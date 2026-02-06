"""
Parse raw Pub/Sub JSON messages and validate required fields.
Routes valid records to 'valid' output, malformed to 'invalid'.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict

import apache_beam as beam
from apache_beam import pvalue

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "feedback_id",
    "customer_id",
    "channel",
    "text",
    "created_at",
]

VALID_TAG = "valid"
INVALID_TAG = "invalid"


class _ParseAndValidateFn(beam.DoFn):

    def process(self, element: bytes):
        try:
            raw = element.decode("utf-8")
            record = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse message: %s", e)
            yield pvalue.TaggedOutput(
                INVALID_TAG,
                {
                    "raw": element.decode("utf-8", errors="replace"),
                    "error": f"parse_error: {e}",
                    "stage": "parse_and_validate",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            return

        missing = [f for f in REQUIRED_FIELDS if f not in record or not record[f]]
        if missing:
            logger.warning(
                "Missing required fields %s in feedback_id=%s",
                missing,
                record.get("feedback_id", "UNKNOWN"),
            )
            yield pvalue.TaggedOutput(
                INVALID_TAG,
                {
                    "raw": raw,
                    "error": f"missing_fields: {missing}",
                    "stage": "parse_and_validate",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            return

        try:
            record["created_at"] = _normalize_timestamp(record["created_at"])
        except ValueError as e:
            logger.warning("Invalid created_at: %s", e)
            yield pvalue.TaggedOutput(
                INVALID_TAG,
                {
                    "raw": raw,
                    "error": f"invalid_timestamp: {e}",
                    "stage": "parse_and_validate",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            return

        record["feedback_text"] = _sanitize_text(record.pop("text"))
        record["channel_id"] = record.pop("channel")

        yield pvalue.TaggedOutput(VALID_TAG, record)


def _normalize_timestamp(ts_value: str) -> str:
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(ts_value, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            continue
    raise ValueError(f"Unsupported timestamp format: {ts_value}")


def _sanitize_text(text: str) -> str:
    text = text.strip()
    text = " ".join(text.split())
    return text


class ParseAndValidate(beam.PTransform):

    def expand(self, pcoll):
        return pcoll | "ParseValidate" >> beam.ParDo(
            _ParseAndValidateFn()
        ).with_outputs(VALID_TAG, INVALID_TAG)
