"""
BigQuery writer: streams enriched feedback records into the fact_feedback table.
"""

import apache_beam as beam
from apache_beam.io.gcp.bigquery import WriteToBigQuery as BQWrite


FACT_FEEDBACK_SCHEMA = {
    "fields": [
        {"name": "feedback_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "product_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "channel_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "feedback_text", "type": "STRING", "mode": "REQUIRED"},
        {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "feedback_date", "type": "DATE", "mode": "REQUIRED"},
        {"name": "hour_of_day", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "day_of_week", "type": "STRING", "mode": "NULLABLE"},
        {"name": "is_weekend", "type": "BOOLEAN", "mode": "NULLABLE"},
        {"name": "locale", "type": "STRING", "mode": "NULLABLE"},
        {"name": "sentiment_label", "type": "STRING", "mode": "REQUIRED"},
        {"name": "sentiment_score", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "topic", "type": "STRING", "mode": "REQUIRED"},
        {"name": "summary", "type": "STRING", "mode": "NULLABLE"},
        {"name": "ingestion_ts", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}


class WriteToBigQueryFact(beam.PTransform):

    def __init__(self, table: str):
        super().__init__()
        self._table = table

    def expand(self, pcoll):
        return pcoll | "StreamToBigQuery" >> BQWrite(
            table=self._table,
            schema=FACT_FEEDBACK_SCHEMA,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
            method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
            insert_retry_strategy=beam.io.gcp.bigquery_tools.RetryStrategy.RETRY_ON_TRANSIENT_ERROR,
        )
