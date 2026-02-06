terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "feedback-pipeline-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_pubsub_topic" "feedback_ingest" {
  name = "${var.env}-feedback-ingest"

  message_retention_duration = "86400s"

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_pubsub_subscription" "feedback_beam" {
  name  = "${var.env}-feedback-beam-sub"
  topic = google_pubsub_topic.feedback_ingest.id

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  expiration_policy {
    ttl = ""
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.feedback_dead_letter.id
    max_delivery_attempts = 5
  }

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_pubsub_topic" "feedback_dead_letter" {
  name = "${var.env}-feedback-dead-letter"

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_pubsub_subscription" "dead_letter_sub" {
  name  = "${var.env}-feedback-dead-letter-sub"
  topic = google_pubsub_topic.feedback_dead_letter.id

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_storage_bucket" "feedback_raw" {
  name          = "${var.project_id}-${var.env}-feedback-raw"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  versioning {
    enabled = true
  }

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_storage_bucket" "feedback_dead_letter" {
  name          = "${var.project_id}-${var.env}-feedback-dead-letter"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_bigquery_dataset" "feedback" {
  dataset_id    = "${var.env}_feedback_intelligence"
  friendly_name = "Feedback Intelligence (${var.env})"
  description   = "Star schema for real-time customer feedback intelligence pipeline"
  location      = var.bq_location

  default_table_expiration_ms     = null
  default_partition_expiration_ms = null

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_bigquery_table" "fact_feedback" {
  dataset_id          = google_bigquery_dataset.feedback.dataset_id
  table_id            = "fact_feedback"
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "feedback_date"
  }

  clustering = ["customer_id", "sentiment_label", "topic"]

  schema = file("${path.module}/schemas/fact_feedback.json")

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_bigquery_table" "dim_customer" {
  dataset_id          = google_bigquery_dataset.feedback.dataset_id
  table_id            = "dim_customer"
  deletion_protection = true

  schema = file("${path.module}/schemas/dim_customer.json")

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_bigquery_table" "dim_channel" {
  dataset_id          = google_bigquery_dataset.feedback.dataset_id
  table_id            = "dim_channel"
  deletion_protection = true

  schema = file("${path.module}/schemas/dim_channel.json")

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_bigquery_table" "dim_product" {
  dataset_id          = google_bigquery_dataset.feedback.dataset_id
  table_id            = "dim_product"
  deletion_protection = true

  schema = file("${path.module}/schemas/dim_product.json")

  labels = {
    environment = var.env
    managed_by  = "terraform"
  }
}

resource "google_service_account" "beam_pipeline" {
  account_id   = "${var.env}-beam-pipeline"
  display_name = "Beam Pipeline Service Account (${var.env})"
  description  = "Service account for the Dataflow feedback pipeline"
}

resource "google_service_account" "alert_function" {
  account_id   = "${var.env}-alert-fn"
  display_name = "Alert Cloud Function SA (${var.env})"
  description  = "Service account for the sentiment alerting Cloud Function"
}

resource "google_project_iam_member" "beam_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.beam_pipeline.email}"
}

resource "google_project_iam_member" "beam_pubsub_viewer" {
  project = var.project_id
  role    = "roles/pubsub.viewer"
  member  = "serviceAccount:${google_service_account.beam_pipeline.email}"
}

resource "google_project_iam_member" "beam_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.beam_pipeline.email}"
}

resource "google_project_iam_member" "beam_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.beam_pipeline.email}"
}

resource "google_project_iam_member" "beam_gcs_writer" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.beam_pipeline.email}"
}

resource "google_project_iam_member" "beam_dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.beam_pipeline.email}"
}

resource "google_project_iam_member" "beam_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.beam_pipeline.email}"
}

resource "google_project_iam_member" "alert_bq_reader" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.alert_function.email}"
}

resource "google_project_iam_member" "alert_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.alert_function.email}"
}
