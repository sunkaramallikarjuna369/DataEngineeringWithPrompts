output "pubsub_topic_id" {
  description = "Pub/Sub topic ID for feedback ingestion"
  value       = google_pubsub_topic.feedback_ingest.id
}

output "pubsub_subscription_id" {
  description = "Pub/Sub subscription ID for Beam pipeline"
  value       = google_pubsub_subscription.feedback_beam.id
}

output "bq_dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.feedback.dataset_id
}

output "bq_fact_table_id" {
  description = "BigQuery fact_feedback table ID"
  value       = google_bigquery_table.fact_feedback.table_id
}

output "raw_bucket_name" {
  description = "GCS bucket for raw feedback backups"
  value       = google_storage_bucket.feedback_raw.name
}

output "dead_letter_bucket_name" {
  description = "GCS bucket for dead-letter messages"
  value       = google_storage_bucket.feedback_dead_letter.name
}

output "beam_service_account_email" {
  description = "Service account email for the Beam pipeline"
  value       = google_service_account.beam_pipeline.email
}

output "alert_service_account_email" {
  description = "Service account email for the alerting function"
  value       = google_service_account.alert_function.email
}
