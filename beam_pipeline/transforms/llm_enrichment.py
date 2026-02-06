"""
LLM enrichment transform: calls the prompt_engine to classify
sentiment, topic, and generate a summary for each feedback record.
"""

import logging
from datetime import datetime
from typing import Dict

import apache_beam as beam
from apache_beam import pvalue

from beam_pipeline.prompt_engine.engine import PromptEngine
from beam_pipeline.prompt_engine.validator import OutputValidator

logger = logging.getLogger(__name__)

LLM_SUCCESS_TAG = "llm_success"
LLM_FAILURE_TAG = "llm_failure"


class _LLMEnrichmentFn(beam.DoFn):

    def __init__(self, project: str, location: str, model_name: str):
        self._project = project
        self._location = location
        self._model_name = model_name
        self._engine = None
        self._validator = None

    def setup(self):
        self._engine = PromptEngine(
            project=self._project,
            location=self._location,
            model_name=self._model_name,
        )
        self._validator = OutputValidator()

    def process(self, record: Dict):
        feedback_text = record.get("feedback_text", "")
        locale = record.get("locale", "en")

        try:
            llm_response = self._engine.classify_feedback(
                text=feedback_text,
                locale=locale,
            )

            validated = self._validator.validate(llm_response)

            record["sentiment_label"] = validated["sentiment_label"]
            record["sentiment_score"] = validated["sentiment_score"]
            record["topic"] = validated["topic"]
            record["summary"] = validated["summary"]
            record["ingestion_ts"] = datetime.utcnow().strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )

            yield pvalue.TaggedOutput(LLM_SUCCESS_TAG, record)

        except Exception as e:
            logger.error(
                "LLM enrichment failed for feedback_id=%s: %s",
                record.get("feedback_id", "UNKNOWN"),
                e,
            )
            yield pvalue.TaggedOutput(
                LLM_FAILURE_TAG,
                {
                    "raw": str(record),
                    "error": f"llm_enrichment_error: {e}",
                    "stage": "llm_enrichment",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )


class LLMEnrichment(beam.PTransform):

    def __init__(self, project: str, location: str, model_name: str):
        super().__init__()
        self._project = project
        self._location = location
        self._model_name = model_name

    def expand(self, pcoll):
        return pcoll | "ClassifyWithLLM" >> beam.ParDo(
            _LLMEnrichmentFn(
                project=self._project,
                location=self._location,
                model_name=self._model_name,
            )
        ).with_outputs(LLM_SUCCESS_TAG, LLM_FAILURE_TAG)
