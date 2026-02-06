# Real-Time Customer Feedback Intelligence Pipeline

Production-ready real-time pipeline on Google Cloud that ingests customer feedback, classifies sentiment and topic using LLMs, stores structured results in BigQuery, and powers dashboards plus alerting for negative sentiment spikes.

## Architecture

```
Customer Feedback (app/web/email/support)
  → Pub/Sub
  → Dataflow (Apache Beam - parse, validate, enrich)
  → Vertex AI / LLM (sentiment + topic + summary)
  → BigQuery (star schema: fact_feedback + dimensions)
  → Looker Studio dashboards + Cloud Function alerts
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full system design.

## Repo Structure

```
infra/                  Terraform IaC (Pub/Sub, BigQuery, GCS, IAM)
beam_pipeline/          Apache Beam streaming pipeline
  transforms/           Parse, validate, temporal enrichment, LLM enrichment
  io/                   Pub/Sub reader, BigQuery writer, dead-letter writer
  prompt_engine/        Prompt template, LLM engine, output validator
sql/                    BigQuery DDL + analytics queries
alerting/               Cloud Function for negative sentiment spike alerts
docs/                   ARCHITECTURE.md, PROMPTS.md, RUNBOOK.md
```

## Quick Start

### 1. Deploy Infrastructure

```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Edit with your GCP project settings
terraform init && terraform apply
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Pipeline (Local)

```bash
python -m beam_pipeline.main \
  --input_subscription=projects/PROJECT/subscriptions/dev-feedback-beam-sub \
  --bq_table=PROJECT:dev_feedback_intelligence.fact_feedback \
  --dead_letter_bucket=gs://PROJECT-dev-feedback-dead-letter/dead-letter/ \
  --llm_project=PROJECT \
  --runner=DirectRunner
```

### 4. Run Pipeline (Dataflow)

```bash
python -m beam_pipeline.main \
  --input_subscription=projects/PROJECT/subscriptions/dev-feedback-beam-sub \
  --bq_table=PROJECT:dev_feedback_intelligence.fact_feedback \
  --dead_letter_bucket=gs://PROJECT-dev-feedback-dead-letter/dead-letter/ \
  --llm_project=PROJECT \
  --runner=DataflowRunner \
  --project=PROJECT \
  --region=us-central1 \
  --streaming
```

### 5. Deploy Alerting

```bash
cd alerting/
gcloud functions deploy sentiment_alert \
  --runtime python311 \
  --trigger-http \
  --entry-point check_negative_sentiment \
  --set-env-vars PROJECT_ID=PROJECT,THRESHOLD=0.30
```

## Key Features

- **LLM-powered classification**: Sentiment (5-level), topic, and summary via Vertex AI Gemini
- **Robust prompt engineering**: Few-shot examples, guardrails for edge cases, output validation
- **Star schema**: Partitioned and clustered BigQuery tables for fast analytics
- **Dead-letter handling**: Failed messages routed to GCS for debugging
- **Automated alerting**: Hourly negative sentiment spike detection via Cloud Function
- **Infrastructure as Code**: Full Terraform configuration with least-privilege IAM

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and component details
- [Prompt Strategy](docs/PROMPTS.md) - LLM prompt engineering approach
- [Runbook](docs/RUNBOOK.md) - Deployment, monitoring, and troubleshooting
