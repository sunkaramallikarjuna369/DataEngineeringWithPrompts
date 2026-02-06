"""
Real-Time Customer Feedback Intelligence Pipeline

Apache Beam streaming pipeline that:
1. Reads JSON messages from Pub/Sub
2. Validates and cleans incoming data
3. Enriches with temporal features
4. Classifies sentiment and topic via LLM (prompt_engine)
5. Writes enriched records to BigQuery; failures to GCS dead-letter
"""

import argparse
import logging

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions

from beam_pipeline.transforms.parse_and_validate import ParseAndValidate
from beam_pipeline.transforms.enrich_temporal import EnrichTemporal
from beam_pipeline.transforms.llm_enrichment import LLMEnrichment
from beam_pipeline.io.pubsub_reader import ReadFromFeedbackPubSub
from beam_pipeline.io.bigquery_writer import WriteToBigQueryFact
from beam_pipeline.io.dead_letter_writer import WriteToDeadLetter

logger = logging.getLogger(__name__)

VALID_TAG = "valid"
INVALID_TAG = "invalid"
LLM_SUCCESS_TAG = "llm_success"
LLM_FAILURE_TAG = "llm_failure"


def build_pipeline_args():
    parser = argparse.ArgumentParser(
        description="Customer Feedback Intelligence Streaming Pipeline"
    )
    parser.add_argument(
        "--input_subscription",
        required=True,
        help="Pub/Sub subscription path: projects/<project>/subscriptions/<sub>",
    )
    parser.add_argument(
        "--bq_table",
        required=True,
        help="BigQuery output table: project:dataset.fact_feedback",
    )
    parser.add_argument(
        "--dead_letter_bucket",
        required=True,
        help="GCS bucket for dead-letter output: gs://bucket-name/dead-letter/",
    )
    parser.add_argument(
        "--llm_project",
        required=True,
        help="GCP project ID for Vertex AI LLM calls",
    )
    parser.add_argument(
        "--llm_location",
        default="us-central1",
        help="Vertex AI region (default: us-central1)",
    )
    parser.add_argument(
        "--llm_model",
        default="gemini-1.5-flash",
        help="Vertex AI model name (default: gemini-1.5-flash)",
    )
    return parser.parse_known_args()


def run():
    known_args, pipeline_args = build_pipeline_args()

    options = PipelineOptions(pipeline_args)
    options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=options) as p:
        raw_messages = p | "ReadPubSub" >> ReadFromFeedbackPubSub(
            subscription=known_args.input_subscription
        )

        parsed = raw_messages | "ParseAndValidate" >> ParseAndValidate()

        valid_records = parsed[VALID_TAG]
        invalid_records = parsed[INVALID_TAG]

        enriched_temporal = valid_records | "EnrichTemporal" >> EnrichTemporal()

        llm_results = enriched_temporal | "LLMEnrichment" >> LLMEnrichment(
            project=known_args.llm_project,
            location=known_args.llm_location,
            model_name=known_args.llm_model,
        )

        llm_success = llm_results[LLM_SUCCESS_TAG]
        llm_failure = llm_results[LLM_FAILURE_TAG]

        llm_success | "WriteToBigQuery" >> WriteToBigQueryFact(
            table=known_args.bq_table
        )

        (
            [invalid_records, llm_failure]
            | "FlattenFailures" >> beam.Flatten()
            | "WriteDeadLetter" >> WriteToDeadLetter(
                output_path=known_args.dead_letter_bucket
            )
        )

    logger.info("Pipeline completed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
