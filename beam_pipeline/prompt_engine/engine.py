"""
Prompt engine: orchestrates LLM calls for feedback classification.

Uses Vertex AI Generative AI SDK to send prompts and receive
structured JSON responses. Falls back to defaults on failure.
"""

import logging
from typing import Optional

from beam_pipeline.prompt_engine.template import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 5

SHORT_TEXT_RESPONSE = (
    '{"sentiment_label": "neutral", "sentiment_score": 0.5, '
    '"topic": "other", "summary": "Insufficient text for classification."}'
)


class PromptEngine:

    def __init__(
        self,
        project: str,
        location: str,
        model_name: str = "gemini-1.5-flash",
        max_output_tokens: int = 256,
        temperature: float = 0.1,
    ):
        self._project = project
        self._location = location
        self._model_name = model_name
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._model = None

    def _get_model(self):
        if self._model is None:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            vertexai.init(project=self._project, location=self._location)
            self._model = GenerativeModel(
                model_name=self._model_name,
                system_instruction=SYSTEM_PROMPT,
            )
        return self._model

    def classify_feedback(
        self,
        text: str,
        locale: str = "en",
    ) -> str:
        if not text or len(text.split()) < MIN_TEXT_LENGTH:
            logger.info("Text too short for classification, returning defaults.")
            return SHORT_TEXT_RESPONSE

        from vertexai.generative_models import GenerationConfig

        model = self._get_model()
        user_prompt = build_user_prompt(text=text, locale=locale)

        generation_config = GenerationConfig(
            max_output_tokens=self._max_output_tokens,
            temperature=self._temperature,
            response_mime_type="application/json",
        )

        response = model.generate_content(
            contents=user_prompt,
            generation_config=generation_config,
        )

        return response.text
