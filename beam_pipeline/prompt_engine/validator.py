"""
Output validator for LLM responses.

Validates JSON structure, enforces allowed label/topic values,
and falls back to safe defaults on error.
"""

import json
import logging
from typing import Any, Dict, Optional

from beam_pipeline.prompt_engine.template import ALLOWED_SENTIMENT_LABELS, ALLOWED_TOPICS

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = {
    "sentiment_label": "neutral",
    "sentiment_score": 0.5,
    "topic": "other",
    "summary": "Classification failed; default values applied.",
}

REQUIRED_KEYS = {"sentiment_label", "sentiment_score", "topic", "summary"}


class OutputValidator:

    def validate(self, raw_response: str) -> Dict[str, Any]:
        parsed = self._parse_json(raw_response)
        if parsed is None:
            logger.warning("LLM response is not valid JSON, using defaults.")
            return dict(DEFAULT_OUTPUT)

        validated = {}

        validated["sentiment_label"] = self._validate_sentiment_label(
            parsed.get("sentiment_label")
        )
        validated["sentiment_score"] = self._validate_sentiment_score(
            parsed.get("sentiment_score")
        )
        validated["topic"] = self._validate_topic(parsed.get("topic"))
        validated["summary"] = self._validate_summary(parsed.get("summary"))

        return validated

    def _parse_json(self, raw: str) -> Optional[Dict]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
            logger.warning("LLM returned JSON but not a dict: %s", type(result))
            return None
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return None

    def _validate_sentiment_label(self, value: Any) -> str:
        if isinstance(value, str) and value.lower() in ALLOWED_SENTIMENT_LABELS:
            return value.lower()
        logger.warning(
            "Invalid sentiment_label '%s', defaulting to 'neutral'.", value
        )
        return "neutral"

    def _validate_sentiment_score(self, value: Any) -> float:
        try:
            score = float(value)
            return max(0.0, min(1.0, score))
        except (TypeError, ValueError):
            logger.warning(
                "Invalid sentiment_score '%s', defaulting to 0.5.", value
            )
            return 0.5

    def _validate_topic(self, value: Any) -> str:
        if isinstance(value, str) and value.lower() in ALLOWED_TOPICS:
            return value.lower()
        logger.warning("Invalid topic '%s', defaulting to 'other'.", value)
        return "other"

    def _validate_summary(self, value: Any) -> str:
        if isinstance(value, str) and len(value.strip()) > 0:
            summary = value.strip()
            if len(summary) > 500:
                return summary[:497] + "..."
            return summary
        logger.warning("Invalid or empty summary, using default.")
        return "No summary available."
