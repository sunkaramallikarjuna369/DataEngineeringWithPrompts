# Architecture: Real-Time Customer Feedback Intelligence Pipeline

## Overview

This system ingests customer feedback from multiple channels in real time, enriches it with LLM-based sentiment and topic classification, stores structured results in BigQuery, and powers dashboards plus automated alerting for negative sentiment spikes.

## High-Level Flow

```
Customer Feedback (app / web / email / support tickets)
        │
        ▼
  ┌─────────────┐
  │   Pub/Sub    │  ← JSON messages from multiple channels
  │   Topic      │
  └──────┬──────┘
         │
         ▼
  ┌─────────────────┐
  │   Dataflow       │  ← Apache Beam (Python) streaming pipeline
  │   (Beam)         │
  │                  │
  │  1. Parse JSON   │
  │  2. Validate     │
  │  3. Clean text   │
  │  4. Enrich time  │
  │  5. Call LLM     │
  └───┬─────────┬───┘
      │         │
      ▼         ▼
 ┌────────┐  ┌────────────┐
 │BigQuery│  │ GCS Dead   │  ← Failed / malformed messages
 │ (Star  │  │ Letter     │
 │Schema) │  └────────────┘
 └───┬────┘
     │
     ▼
 ┌──────────────────┐
 │ Looker Studio /  │  ← Dashboards + SQL views
 │ Analytics        │
 └───────┬──────────┘
         │
         ▼
 ┌──────────────────┐
 │ Cloud Function   │  ← Scheduled hourly alerting
 │ + Scheduler      │
 └──────────────────┘
```

## Components

### 1. Ingestion Layer: Pub/Sub

- **Topic**: `{env}-feedback-ingest`
- **Subscription**: `{env}-feedback-beam-sub` (pull, used by Dataflow)
- **Dead-letter topic**: `{env}-feedback-dead-letter` (after 5 delivery attempts)
- **Message format**: JSON with fields `feedback_id`, `customer_id`, `channel`, `text`, `created_at`, `product_id`, `locale`
- **Retention**: 24h on topic, 7 days on subscription

### 2. Processing Layer: Dataflow (Apache Beam)

The streaming pipeline runs on Google Cloud Dataflow and consists of:

| Stage | Module | Description |
|-------|--------|-------------|
| Parse & Validate | `transforms/parse_and_validate.py` | Decode JSON, check required fields, normalize timestamps, route invalid to dead-letter |
| Temporal Enrichment | `transforms/enrich_temporal.py` | Extract `feedback_date`, `hour_of_day`, `day_of_week`, `is_weekend` |
| LLM Enrichment | `transforms/llm_enrichment.py` | Call Vertex AI via `prompt_engine` to get sentiment, topic, summary |

### 3. LLM / Prompt Engine

- **Model**: Vertex AI Gemini 1.5 Flash (configurable)
- **Prompt strategy**: System instructions + few-shot examples + strict JSON output
- **Guardrails**:
  - Short text (< 5 words) → default neutral
  - Unsupported language → default neutral
  - Uncertainty → bias toward neutral with low confidence score
- **Output validator**: Parses JSON, enforces allowed values, falls back to defaults
- See [PROMPTS.md](PROMPTS.md) for full prompt strategy documentation

### 4. Storage Layer: BigQuery (Star Schema)

| Table | Type | Partitioning | Clustering |
|-------|------|-------------|------------|
| `fact_feedback` | Fact | `feedback_date` (DAY) | `customer_id`, `sentiment_label`, `topic` |
| `dim_customer` | Dimension | - | - |
| `dim_channel` | Dimension | - | - |
| `dim_product` | Dimension | - | - |

### 5. Analytics & Dashboards

- **Looker Studio** dashboards connected to BigQuery
- Key views:
  - Sentiment trend over time
  - Top negative topics by product/region
  - Volume by channel
  - Customer-level complaint summary

### 6. Alerting

- **Cloud Scheduler** triggers a Cloud Function every hour
- Cloud Function queries BigQuery for negative sentiment ratio
- If `negative + very_negative > threshold%` in last hour → alert
- Alert delivery via logging (configurable: SendGrid, Cloud Monitoring)

## Infrastructure

All infrastructure is managed via **Terraform** in `/infra/`:
- Pub/Sub topics and subscriptions
- BigQuery dataset and tables
- GCS buckets (raw backup, dead-letter)
- Service accounts with least-privilege IAM

## Security

- Separate service accounts for pipeline and alerting
- Least-privilege IAM roles:
  - Pipeline SA: Pub/Sub subscriber, BQ data editor, GCS object creator, Dataflow worker, Vertex AI user
  - Alert SA: BQ data viewer, BQ job user
- No secrets in code; credentials via GCP service account binding

## Repo Structure

```
/
├── infra/                        # Terraform IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   └── schemas/                  # BQ table schemas (JSON)
│       ├── fact_feedback.json
│       ├── dim_customer.json
│       ├── dim_channel.json
│       └── dim_product.json
├── beam_pipeline/                # Apache Beam streaming pipeline
│   ├── main.py                   # Pipeline entrypoint
│   ├── transforms/
│   │   ├── parse_and_validate.py
│   │   ├── enrich_temporal.py
│   │   └── llm_enrichment.py
│   ├── io/
│   │   ├── pubsub_reader.py
│   │   ├── bigquery_writer.py
│   │   └── dead_letter_writer.py
│   └── prompt_engine/
│       ├── template.py           # Prompt templates + few-shot examples
│       ├── engine.py             # LLM orchestration (Vertex AI)
│       └── validator.py          # Output validation + fallbacks
├── sql/
│   ├── ddl.sql                   # BigQuery table DDL
│   └── analytics_queries.sql     # Key analytics + alerting queries
├── alerting/
│   ├── main.py                   # Cloud Function for spike detection
│   └── requirements.txt
├── tests/                        # Unit tests
├── docs/
│   ├── ARCHITECTURE.md           # This file
│   ├── PROMPTS.md                # Prompt strategy documentation
│   └── RUNBOOK.md                # Operational runbook
├── requirements.txt              # Python dependencies
└── README.md
```
