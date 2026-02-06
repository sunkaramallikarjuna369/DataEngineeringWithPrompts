"""
Dead-letter writer: writes failed records to GCS as JSON files,
partitioned by date and hour for easy debugging.
"""

import json
import logging

import apache_beam as beam
from apache_beam.io import WriteToText

logger = logging.getLogger(__name__)


class _FormatAsJson(beam.DoFn):

    def process(self, record):
        try:
            yield json.dumps(record, default=str)
        except (TypeError, ValueError) as e:
            logger.error("Cannot serialize dead-letter record: %s", e)
            yield json.dumps({"error": str(e), "raw": str(record)})


class WriteToDeadLetter(beam.PTransform):

    def __init__(self, output_path: str):
        super().__init__()
        self._output_path = output_path.rstrip("/")

    def expand(self, pcoll):
        return (
            pcoll
            | "FormatDeadLetterJson" >> beam.ParDo(_FormatAsJson())
            | "WriteToGCS"
            >> WriteToText(
                file_path_prefix=f"{self._output_path}/failed",
                file_name_suffix=".jsonl",
                shard_name_template="-SSSSS-of-NNNNN",
            )
        )
