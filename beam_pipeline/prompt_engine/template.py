"""
Prompt template for LLM-based feedback classification.

Defines the system prompt, user prompt template, few-shot examples,
allowed values, and the expected JSON output schema.
"""

ALLOWED_SENTIMENT_LABELS = [
    "very_negative",
    "negative",
    "neutral",
    "positive",
    "very_positive",
]

ALLOWED_TOPICS = [
    "billing",
    "performance",
    "ux",
    "support",
    "reliability",
    "security",
    "onboarding",
    "documentation",
    "pricing",
    "feature_request",
    "bug",
    "integration",
    "other",
]

OUTPUT_SCHEMA = {
    "sentiment_label": "string (one of: very_negative, negative, neutral, positive, very_positive)",
    "sentiment_score": "float (0.0 to 1.0, confidence in the sentiment classification)",
    "topic": "string (short category from the allowed list)",
    "summary": "string (1-2 sentence summary of the feedback)",
}

SYSTEM_PROMPT = """You are an expert customer feedback analyst. Your job is to analyze customer feedback and classify it accurately.

You MUST return a valid JSON object with exactly these fields:
- "sentiment_label": one of ["very_negative", "negative", "neutral", "positive", "very_positive"]
- "sentiment_score": a float between 0.0 and 1.0 representing your confidence in the sentiment classification
- "topic": one of ["billing", "performance", "ux", "support", "reliability", "security", "onboarding", "documentation", "pricing", "feature_request", "bug", "integration", "other"]
- "summary": a concise 1-2 sentence summary of the feedback

Rules:
1. Return ONLY the JSON object. No markdown, no explanation, no code fences.
2. If the text is too short (fewer than 5 words) or unintelligible, return sentiment_label="neutral", sentiment_score=0.5, topic="other", summary="Insufficient text for classification."
3. If the language is not English and you cannot confidently classify, return sentiment_label="neutral", sentiment_score=0.3, topic="other", summary="Non-English or unsupported language."
4. If you are uncertain about the sentiment, bias toward "neutral" and lower the sentiment_score.
5. The topic should reflect the PRIMARY concern. If multiple topics apply, pick the most dominant one.
6. The summary should capture the core issue or praise in the customer's own context."""

FEW_SHOT_EXAMPLES = [
    {
        "input": "I've been trying to cancel my subscription for 3 weeks and nobody responds to my emails. This is absolutely terrible service. I'm going to dispute the charge with my bank.",
        "output": {
            "sentiment_label": "very_negative",
            "sentiment_score": 0.95,
            "topic": "billing",
            "summary": "Customer unable to cancel subscription after 3 weeks of unanswered emails, threatening bank dispute.",
        },
    },
    {
        "input": "The app crashes every time I try to upload a file larger than 10MB. Started happening after the last update.",
        "output": {
            "sentiment_label": "negative",
            "sentiment_score": 0.88,
            "topic": "bug",
            "summary": "App crashes on file uploads over 10MB since the latest update.",
        },
    },
    {
        "input": "Just signed up yesterday. The onboarding wizard was straightforward and I had my first dashboard running in under 10 minutes. Nice work!",
        "output": {
            "sentiment_label": "positive",
            "sentiment_score": 0.90,
            "topic": "onboarding",
            "summary": "New user praises the smooth onboarding experience, set up first dashboard in under 10 minutes.",
        },
    },
    {
        "input": "It works fine I guess. Nothing special but gets the job done.",
        "output": {
            "sentiment_label": "neutral",
            "sentiment_score": 0.70,
            "topic": "other",
            "summary": "Customer finds the product functional but unremarkable.",
        },
    },
    {
        "input": "This is hands down the best analytics tool I've ever used. The real-time dashboards are incredible and the team's support is world-class. Already recommended it to 5 colleagues.",
        "output": {
            "sentiment_label": "very_positive",
            "sentiment_score": 0.97,
            "topic": "ux",
            "summary": "Enthusiastic praise for analytics capabilities, real-time dashboards, and support quality; actively recommending to others.",
        },
    },
]


def build_user_prompt(text: str, locale: str = "en") -> str:
    examples_block = "\n\n".join(
        [
            f'Example {i+1}:\nInput: "{ex["input"]}"\nOutput: {_format_json(ex["output"])}'
            for i, ex in enumerate(FEW_SHOT_EXAMPLES)
        ]
    )

    return f"""{examples_block}

Now classify the following customer feedback:
Locale: {locale}
Input: "{text}"
Output:"""


def _format_json(obj: dict) -> str:
    import json

    return json.dumps(obj, indent=None)
