# Runbook: Customer Feedback Intelligence Pipeline

## Table of Contents

1. [Deployment](#deployment)
2. [Running the Pipeline](#running-the-pipeline)
3. [Monitoring](#monitoring)
4. [Alerting](#alerting)
5. [Troubleshooting](#troubleshooting)
6. [Maintenance](#maintenance)

---

## Deployment

### Prerequisites

- GCP project with billing enabled
- Terraform >= 1.5.0 installed
- Python 3.9+ with pip
- `gcloud` CLI authenticated with appropriate permissions
- Vertex AI API enabled in the project

### 1. Deploy Infrastructure

```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project settings

terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### 2. Install Pipeline Dependencies

```bash
pip install -r requirements.txt
```

### 3. Deploy the Dataflow Pipeline

```bash
python -m beam_pipeline.main \
  --input_subscription=projects/<PROJECT>/subscriptions/<ENV>-feedback-beam-sub \
  --bq_table=<PROJECT>:<ENV>_feedback_intelligence.fact_feedback \
  --dead_letter_bucket=gs://<PROJECT>-<ENV>-feedback-dead-letter/dead-letter/ \
  --llm_project=<PROJECT> \
  --llm_location=us-central1 \
  --llm_model=gemini-1.5-flash \
  --runner=DataflowRunner \
  --project=<PROJECT> \
  --region=us-central1 \
  --temp_location=gs://<PROJECT>-<ENV>-feedback-raw/temp/ \
  --staging_location=gs://<PROJECT>-<ENV>-feedback-raw/staging/ \
  --service_account_email=<ENV>-beam-pipeline@<PROJECT>.iam.gserviceaccount.com \
  --streaming
```

### 4. Deploy Alerting Cloud Function

```bash
cd alerting/
gcloud functions deploy sentiment_alert \
  --runtime python311 \
  --trigger-http \
  --entry-point check_negative_sentiment \
  --service-account <ENV>-alert-fn@<PROJECT>.iam.gserviceaccount.com \
  --set-env-vars PROJECT_ID=<PROJECT>,DATASET=<ENV>_feedback_intelligence,THRESHOLD=0.30,ALERT_EMAIL=ops@company.com \
  --region us-central1
```

### 5. Set Up Cloud Scheduler

```bash
gcloud scheduler jobs create http sentiment-alert-hourly \
  --schedule="0 * * * *" \
  --uri="https://<REGION>-<PROJECT>.cloudfunctions.net/sentiment_alert" \
  --http-method=GET \
  --oidc-service-account-email=<ENV>-alert-fn@<PROJECT>.iam.gserviceaccount.com \
  --location=us-central1
```

---

## Running the Pipeline

### Local Testing (DirectRunner)

```bash
python -m beam_pipeline.main \
  --input_subscription=projects/<PROJECT>/subscriptions/<ENV>-feedback-beam-sub \
  --bq_table=<PROJECT>:<ENV>_feedback_intelligence.fact_feedback \
  --dead_letter_bucket=gs://<PROJECT>-<ENV>-feedback-dead-letter/dead-letter/ \
  --llm_project=<PROJECT> \
  --runner=DirectRunner
```

### Publish Test Messages

```bash
gcloud pubsub topics publish <ENV>-feedback-ingest \
  --message='{
    "feedback_id": "test-001",
    "customer_id": "cust-123",
    "channel": "web_form",
    "text": "The dashboard is slow and keeps timing out when I load reports.",
    "created_at": "2026-02-06T10:30:00Z",
    "product_id": "prod-analytics",
    "locale": "en-US"
  }'
```

---

## Monitoring

### Dataflow Job Health

```bash
gcloud dataflow jobs list --region=us-central1 --status=active
gcloud dataflow jobs describe <JOB_ID> --region=us-central1
```

### Key Metrics to Watch

| Metric | Where | Threshold |
|--------|-------|-----------|
| System lag | Dataflow UI | < 60s |
| Data freshness | Dataflow UI | < 5 min |
| Failed inserts | BQ streaming buffer | 0 |
| Dead-letter volume | GCS bucket | < 1% of total |
| LLM latency (p99) | Cloud Monitoring | < 5s |
| Pub/Sub backlog | Pub/Sub metrics | < 1000 messages |

### BigQuery Monitoring Query

```sql
SELECT
  DATE(ingestion_ts) AS ingest_date,
  COUNT(*) AS records_ingested,
  MIN(ingestion_ts) AS earliest,
  MAX(ingestion_ts) AS latest
FROM `feedback_intelligence.fact_feedback`
WHERE ingestion_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY ingest_date
ORDER BY ingest_date DESC;
```

---

## Alerting

### How It Works

1. Cloud Scheduler triggers the `sentiment_alert` Cloud Function every hour
2. The function queries BigQuery for negative sentiment ratio in the last hour
3. If `negative + very_negative > 30%` (configurable), an alert is generated
4. Alerts are logged as CRITICAL and optionally sent via email

### Adjusting Threshold

Update the `THRESHOLD` environment variable on the Cloud Function:

```bash
gcloud functions deploy sentiment_alert \
  --update-env-vars THRESHOLD=0.25
```

### Manual Alert Check

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://<REGION>-<PROJECT>.cloudfunctions.net/sentiment_alert
```

---

## Troubleshooting

### Pipeline Not Processing Messages

1. Check Pub/Sub subscription backlog:
   ```bash
   gcloud pubsub subscriptions describe <ENV>-feedback-beam-sub
   ```
2. Check Dataflow job status and errors in the Dataflow UI
3. Verify service account has `pubsub.subscriber` role

### LLM Enrichment Failures

1. Check dead-letter GCS bucket for failed records
2. Look for `llm_enrichment_error` in dead-letter JSON files
3. Verify Vertex AI API is enabled and SA has `aiplatform.user` role
4. Check Vertex AI quotas in the GCP console

### BigQuery Write Failures

1. Check Dataflow job logs for BQ insert errors
2. Verify table schema matches pipeline output schema
3. Check BQ streaming buffer metrics for throttling
4. Ensure SA has `bigquery.dataEditor` and `bigquery.jobUser` roles

### Malformed Messages Going to Dead Letter

1. Download recent dead-letter files from GCS:
   ```bash
   gsutil ls gs://<BUCKET>/dead-letter/
   gsutil cat gs://<BUCKET>/dead-letter/failed-00000-of-00001.jsonl
   ```
2. Check the `error` field for the failure reason
3. Common issues: missing required fields, invalid timestamp format, non-UTF-8 encoding

---

## Maintenance

### Updating the Prompt

1. Edit `beam_pipeline/prompt_engine/template.py`
2. Test locally with sample feedback
3. Deploy updated pipeline (Dataflow will perform a rolling update)

### Adding New Topics

1. Add the topic to `ALLOWED_TOPICS` in `template.py`
2. Add a few-shot example for the new topic
3. Update `SYSTEM_PROMPT` to include the new topic in the list
4. Update `validator.py` (topics are read from `template.py` automatically)
5. Redeploy pipeline

### Schema Changes

1. Update the JSON schema in `infra/schemas/`
2. Update BQ table schema (BQ supports adding nullable columns without recreation)
3. Update `bigquery_writer.py` schema definition
4. Run `terraform apply`
5. Redeploy pipeline

### Scaling

- **Pub/Sub**: Auto-scales; no action needed
- **Dataflow**: Adjust `--num_workers` and `--max_num_workers` flags
- **BigQuery**: Auto-scales; monitor streaming insert quotas
- **LLM**: Monitor Vertex AI quotas; request increases if needed
