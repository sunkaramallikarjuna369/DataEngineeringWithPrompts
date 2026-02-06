-- =============================================================================
-- Analytics Queries: Customer Feedback Intelligence Pipeline
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Daily Sentiment Trend
-- Shows sentiment distribution per day over the last 30 days.
-- -----------------------------------------------------------------------------
SELECT
  feedback_date,
  sentiment_label,
  COUNT(*)                                           AS feedback_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY feedback_date), 2)
                                                     AS pct_of_day
FROM `feedback_intelligence.fact_feedback`
WHERE feedback_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY feedback_date, sentiment_label
ORDER BY feedback_date DESC, feedback_count DESC;

-- -----------------------------------------------------------------------------
-- 2. Top Negative Topics in Last 7 Days
-- Surfaces the most common complaint categories.
-- -----------------------------------------------------------------------------
SELECT
  topic,
  COUNT(*)                         AS negative_count,
  ROUND(AVG(sentiment_score), 3)   AS avg_confidence
FROM `feedback_intelligence.fact_feedback`
WHERE feedback_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  AND sentiment_label IN ('negative', 'very_negative')
GROUP BY topic
ORDER BY negative_count DESC
LIMIT 20;

-- -----------------------------------------------------------------------------
-- 3. Negative Sentiment by Channel and Product
-- Drill-down view for product and channel owners.
-- -----------------------------------------------------------------------------
SELECT
  dc.channel_name,
  dp.product_name,
  ff.sentiment_label,
  COUNT(*)                         AS feedback_count,
  ROUND(AVG(ff.sentiment_score), 3) AS avg_confidence
FROM `feedback_intelligence.fact_feedback`      ff
JOIN `feedback_intelligence.dim_channel`        dc ON ff.channel_id = dc.channel_id
JOIN `feedback_intelligence.dim_product`        dp ON ff.product_id = dp.product_id
WHERE ff.feedback_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND ff.sentiment_label IN ('negative', 'very_negative')
GROUP BY dc.channel_name, dp.product_name, ff.sentiment_label
ORDER BY feedback_count DESC;

-- -----------------------------------------------------------------------------
-- 4. Volume by Channel (Last 30 Days)
-- Understand which channels generate the most feedback.
-- -----------------------------------------------------------------------------
SELECT
  dc.channel_name,
  dc.channel_type,
  COUNT(*)                                           AS total_feedback,
  COUNTIF(ff.sentiment_label IN ('negative', 'very_negative'))
                                                     AS negative_count,
  ROUND(
    COUNTIF(ff.sentiment_label IN ('negative', 'very_negative')) * 100.0 / COUNT(*), 2
  )                                                  AS negative_pct
FROM `feedback_intelligence.fact_feedback`      ff
JOIN `feedback_intelligence.dim_channel`        dc ON ff.channel_id = dc.channel_id
WHERE ff.feedback_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY dc.channel_name, dc.channel_type
ORDER BY total_feedback DESC;

-- -----------------------------------------------------------------------------
-- 5. Hourly Negative Sentiment Rate (Alerting Query)
-- Used by the alerting Cloud Function to detect negative spikes.
-- Fires when negative+very_negative exceeds the threshold in the last hour.
-- -----------------------------------------------------------------------------
DECLARE negative_threshold FLOAT64 DEFAULT 0.30;  -- 30% threshold

SELECT
  TIMESTAMP_TRUNC(created_at, HOUR) AS hour_bucket,
  COUNT(*)                          AS total_feedback,
  COUNTIF(sentiment_label IN ('negative', 'very_negative'))
                                    AS negative_count,
  ROUND(
    COUNTIF(sentiment_label IN ('negative', 'very_negative')) * 1.0 / COUNT(*), 4
  )                                 AS negative_ratio
FROM `feedback_intelligence.fact_feedback`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
GROUP BY hour_bucket
HAVING negative_ratio > negative_threshold
ORDER BY hour_bucket DESC;

-- -----------------------------------------------------------------------------
-- 6. Customer Feedback Summary (Top Complainers)
-- Identify customers with the most negative feedback for proactive outreach.
-- -----------------------------------------------------------------------------
SELECT
  dcust.customer_id,
  dcust.customer_name,
  dcust.region,
  dcust.tier,
  COUNT(*)                         AS total_feedback,
  COUNTIF(ff.sentiment_label IN ('negative', 'very_negative'))
                                   AS negative_count,
  ARRAY_AGG(DISTINCT ff.topic ORDER BY ff.topic LIMIT 5)
                                   AS top_topics
FROM `feedback_intelligence.fact_feedback`      ff
JOIN `feedback_intelligence.dim_customer`       dcust ON ff.customer_id = dcust.customer_id
WHERE ff.feedback_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY dcust.customer_id, dcust.customer_name, dcust.region, dcust.tier
HAVING negative_count >= 3
ORDER BY negative_count DESC
LIMIT 50;
