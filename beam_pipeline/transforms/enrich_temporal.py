"""
Enrich validated feedback records with temporal features:
- feedback_date (DATE)
- hour_of_day (0-23)
- day_of_week (Monday, Tuesday, ...)
- is_weekend (True/False)
"""

import logging
from datetime import datetime
from typing import Dict

import apache_beam as beam

logger = logging.getLogger(__name__)


class _EnrichTemporalFn(beam.DoFn):

    def process(self, record: Dict):
        try:
            dt = datetime.strptime(record["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
        except (ValueError, KeyError) as e:
            logger.warning("Cannot parse created_at for temporal enrichment: %s", e)
            yield record
            return

        record["feedback_date"] = dt.strftime("%Y-%m-%d")
        record["hour_of_day"] = dt.hour
        record["day_of_week"] = dt.strftime("%A")
        record["is_weekend"] = dt.weekday() >= 5

        yield record


class EnrichTemporal(beam.PTransform):

    def expand(self, pcoll):
        return pcoll | "AddTemporalFeatures" >> beam.ParDo(_EnrichTemporalFn())
