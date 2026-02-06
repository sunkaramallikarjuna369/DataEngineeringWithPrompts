# Prompt Strategy: Customer Feedback Classification

## Overview

This document describes the prompt engineering approach used by the `prompt_engine` module to classify customer feedback using an LLM (Vertex AI Gemini).

## Design Principles

1. **Deterministic output**: Strict JSON schema with `response_mime_type="application/json"`
2. **Constrained labels**: Closed set of sentiment labels and topic categories
3. **Few-shot learning**: 5 diverse examples covering the full sentiment spectrum
4. **Graceful degradation**: Safe defaults for edge cases (short text, non-English, model uncertainty)
5. **Low temperature**: `temperature=0.1` for consistent, reproducible classifications

## Prompt Structure

### System Prompt

The system prompt establishes the LLM's role and strict output rules:

```
You are an expert customer feedback analyst. Your job is to analyze
customer feedback and classify it accurately.

You MUST return a valid JSON object with exactly these fields:
- "sentiment_label": one of [very_negative, negative, neutral, positive, very_positive]
- "sentiment_score": float between 0.0 and 1.0 (confidence)
- "topic": one of [billing, performance, ux, support, reliability, security,
                    onboarding, documentation, pricing, feature_request, bug,
                    integration, other]
- "summary": concise 1-2 sentence summary
```

### Rules Embedded in System Prompt

| Rule | Behavior |
|------|----------|
| Text < 5 words | Return `neutral`, score 0.5, topic `other` |
| Non-English / unsupported language | Return `neutral`, score 0.3, topic `other` |
| Model uncertain | Bias toward `neutral`, lower confidence score |
| Multiple topics | Pick the most dominant one |
| Summary length | 1-2 sentences capturing the core issue |

### User Prompt (Few-Shot)

The user prompt includes 5 examples followed by the actual input:

```
Example 1:
Input: "<feedback text>"
Output: {"sentiment_label": "...", "sentiment_score": ..., "topic": "...", "summary": "..."}

...

Now classify the following customer feedback:
Locale: en
Input: "<actual feedback>"
Output:
```

## Few-Shot Examples

| # | Sentiment | Topic | Description |
|---|-----------|-------|-------------|
| 1 | very_negative | billing | Subscription cancellation ignored for 3 weeks |
| 2 | negative | bug | App crashes on file upload after update |
| 3 | positive | onboarding | Smooth setup, dashboard in 10 minutes |
| 4 | neutral | other | Works fine, nothing special |
| 5 | very_positive | ux | Best analytics tool, recommending to colleagues |

### Why These Examples?

- **Full spectrum coverage**: All 5 sentiment labels represented
- **Topic diversity**: billing, bug, onboarding, other, ux
- **Realistic length variation**: From short neutral to detailed positive
- **Clear sentiment signals**: Each example has unambiguous sentiment markers
- **Actionable summaries**: Show the expected summary style and length

## Allowed Values

### Sentiment Labels
| Label | Description |
|-------|-------------|
| `very_negative` | Strong dissatisfaction, anger, threats to churn |
| `negative` | Clear dissatisfaction, complaints, reported issues |
| `neutral` | No strong sentiment, factual statements, ambivalent |
| `positive` | Satisfaction, appreciation, mild praise |
| `very_positive` | Enthusiastic praise, strong recommendations |

### Topic Categories
| Topic | Description |
|-------|-------------|
| `billing` | Charges, invoices, subscriptions, refunds |
| `performance` | Speed, latency, resource usage |
| `ux` | User experience, UI design, navigation |
| `support` | Customer service interactions |
| `reliability` | Uptime, availability, data loss |
| `security` | Authentication, data privacy, vulnerabilities |
| `onboarding` | Signup, setup, first-time experience |
| `documentation` | Docs quality, tutorials, help content |
| `pricing` | Plan costs, value perception |
| `feature_request` | New capabilities requested |
| `bug` | Software defects, crashes, errors |
| `integration` | Third-party connections, APIs |
| `other` | Anything that doesn't fit above categories |

## Output Validation

The `OutputValidator` class provides post-LLM safety:

1. **JSON parsing**: Strips markdown fences, attempts partial extraction
2. **Sentiment validation**: Must be in allowed list → default: `neutral`
3. **Score validation**: Must be float 0.0-1.0 → default: `0.5`
4. **Topic validation**: Must be in allowed list → default: `other`
5. **Summary validation**: Must be non-empty string ≤ 500 chars

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model_name` | `gemini-1.5-flash` | Vertex AI model to use |
| `max_output_tokens` | 256 | Maximum response length |
| `temperature` | 0.1 | Low for consistency |
| `response_mime_type` | `application/json` | Forces JSON output |

## Iteration Guide

To improve classification accuracy:

1. **Add more few-shot examples** for underrepresented topics
2. **Tune temperature** if outputs are too repetitive (increase) or inconsistent (decrease)
3. **Add topic-specific rules** in the system prompt for ambiguous categories
4. **Monitor validation fallback rates** to identify common LLM output issues
5. **A/B test models**: Compare Gemini Flash vs Pro for accuracy vs latency tradeoffs
