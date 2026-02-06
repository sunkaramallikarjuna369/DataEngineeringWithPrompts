"""
Cloud Function: Negative Sentiment Spike Alert

Triggered by Cloud Scheduler (every hour). Queries BigQuery for the
percentage of negative feedback in the last hour. If above threshold,
sends an alert via email (SendGrid) or logs a critical warning.

Deployment:
  gcloud functions deploy sentiment_alert \
    --runtime python311 \
    --trigger-http \
    --entry-point check_negative_sentiment \
    --service-account <alert-sa>@<project>.iam.gserviceaccount.com \
    --set-env-vars PROJECT_ID=<project>,DATASET=feedback_intelligence,THRESHOLD=0.30,ALERT_EMAIL=ops@company.com
"""

import json
import logging
import os
from typing import Any, Dict

from google.cloud import bigquery

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", "")
DATASET = os.environ.get("DATASET", "feedback_intelligence")
THRESHOLD = float(os.environ.get("THRESHOLD", "0.30"))
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")

ALERT_QUERY = """
SELECT
  TIMESTAMP_TRUNC(created_at, HOUR)   AS hour_bucket,
  COUNT(*)                             AS total_feedback,
  COUNTIF(sentiment_label IN ('negative', 'very_negative'))
                                       AS negative_count,
  SAFE_DIVIDE(
    COUNTIF(sentiment_label IN ('negative', 'very_negative')),
    COUNT(*)
  )                                    AS negative_ratio
FROM `{project}.{dataset}.fact_feedback`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
GROUP BY hour_bucket
HAVING negative_ratio > {threshold}
ORDER BY hour_bucket DESC
"""


def check_negative_sentiment(request) -> Dict[str, Any]:
    client = bigquery.Client(project=PROJECT_ID)

    query = ALERT_QUERY.format(
        project=PROJECT_ID,
        dataset=DATASET,
        threshold=THRESHOLD,
    )

    results = list(client.query(query).result())

    if not results:
        logger.info("No negative sentiment spike detected in the last hour.")
        return {"status": "ok", "message": "No spike detected."}

    alerts = []
    for row in results:
        alert = {
            "hour_bucket": row.hour_bucket.isoformat(),
            "total_feedback": row.total_feedback,
            "negative_count": row.negative_count,
            "negative_ratio": round(row.negative_ratio, 4),
        }
        alerts.append(alert)
        logger.critical(
            "NEGATIVE SENTIMENT SPIKE: %d/%d (%.1f%%) in bucket %s",
            row.negative_count,
            row.total_feedback,
            row.negative_ratio * 100,
            row.hour_bucket.isoformat(),
        )

    _send_alert(alerts)

    return {
        "status": "alert",
        "message": f"Negative sentiment spike detected in {len(alerts)} bucket(s).",
        "details": alerts,
    }


def _send_alert(alerts: list):
    if not ALERT_EMAIL:
        logger.warning("ALERT_EMAIL not configured. Skipping email notification.")
        return

    subject = f"[ALERT] Negative Sentiment Spike Detected ({len(alerts)} bucket(s))"
    body_lines = [
        "Negative sentiment has exceeded the configured threshold.\n",
        f"Threshold: {THRESHOLD * 100:.0f}%\n",
    ]
    for a in alerts:
        body_lines.append(
            f"  - {a['hour_bucket']}: {a['negative_count']}/{a['total_feedback']} "
            f"({a['negative_ratio'] * 100:.1f}%)"
        )
    body_lines.append("\nPlease investigate in Looker Studio or BigQuery.")
    body = "\n".join(body_lines)

    logger.info("Alert prepared for %s:\n%s\n%s", ALERT_EMAIL, subject, body)

    # TODO: Integrate with SendGrid, Mailgun, or Cloud Monitoring
    # notification channel for production email delivery.
    # Example with SendGrid:
    # from sendgrid import SendGridAPIClient
    # from sendgrid.helpers.mail import Mail
    # message = Mail(
    #     from_email="alerts@company.com",
    #     to_emails=ALERT_EMAIL,
    #     subject=subject,
    #     plain_text_content=body,
    # )
    # sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
    # sg.send(message)
