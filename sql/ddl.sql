-- =============================================================================
-- BigQuery DDL: Customer Feedback Intelligence Pipeline (Star Schema)
-- =============================================================================

-- Dataset
CREATE SCHEMA IF NOT EXISTS `feedback_intelligence`
OPTIONS (
  description = 'Star schema for real-time customer feedback intelligence pipeline',
  location = 'US'
);

-- =============================================================================
-- Fact Table: fact_feedback
-- Partitioned by feedback_date, clustered by customer_id, sentiment_label, topic
-- =============================================================================
CREATE TABLE IF NOT EXISTS `feedback_intelligence.fact_feedback` (
  feedback_id     STRING        NOT NULL  OPTIONS (description = 'Unique identifier for the feedback record'),
  customer_id     STRING        NOT NULL  OPTIONS (description = 'FK to dim_customer'),
  product_id      STRING                  OPTIONS (description = 'FK to dim_product'),
  channel_id      STRING        NOT NULL  OPTIONS (description = 'FK to dim_channel'),
  feedback_text   STRING        NOT NULL  OPTIONS (description = 'Raw feedback text from the customer'),
  created_at      TIMESTAMP     NOT NULL  OPTIONS (description = 'Original timestamp when feedback was submitted'),
  feedback_date   DATE          NOT NULL  OPTIONS (description = 'Date extracted from created_at, used for partitioning'),
  hour_of_day     INT64                   OPTIONS (description = 'Hour extracted from created_at (0-23)'),
  day_of_week     STRING                  OPTIONS (description = 'Day of week extracted from created_at'),
  is_weekend      BOOL                    OPTIONS (description = 'Whether created_at falls on a weekend'),
  locale          STRING                  OPTIONS (description = 'Locale of the feedback (e.g., en-US)'),
  sentiment_label STRING        NOT NULL  OPTIONS (description = 'LLM-classified sentiment'),
  sentiment_score FLOAT64                 OPTIONS (description = 'Numeric confidence score from the LLM (0.0-1.0)'),
  topic           STRING        NOT NULL  OPTIONS (description = 'LLM-classified topic category'),
  summary         STRING                  OPTIONS (description = 'LLM-generated 1-2 sentence summary'),
  ingestion_ts    TIMESTAMP     NOT NULL  OPTIONS (description = 'Timestamp when the record was ingested into BigQuery')
)
PARTITION BY feedback_date
CLUSTER BY customer_id, sentiment_label, topic
OPTIONS (
  description = 'Fact table storing enriched customer feedback with LLM-derived sentiment and topic'
);

-- =============================================================================
-- Dimension Table: dim_customer
-- =============================================================================
CREATE TABLE IF NOT EXISTS `feedback_intelligence.dim_customer` (
  customer_id   STRING    NOT NULL  OPTIONS (description = 'Unique customer identifier'),
  customer_name STRING              OPTIONS (description = 'Full name of the customer'),
  email         STRING              OPTIONS (description = 'Customer email address'),
  region        STRING              OPTIONS (description = 'Geographic region of the customer'),
  country       STRING              OPTIONS (description = 'Country code (ISO 3166-1 alpha-2)'),
  signup_date   DATE                OPTIONS (description = 'Date when the customer signed up'),
  tier          STRING              OPTIONS (description = 'Customer tier: free, basic, premium, enterprise'),
  is_active     BOOL                OPTIONS (description = 'Whether the customer account is active'),
  updated_at    TIMESTAMP           OPTIONS (description = 'Last update timestamp for this dimension record')
)
OPTIONS (
  description = 'Customer dimension table'
);

-- =============================================================================
-- Dimension Table: dim_channel
-- =============================================================================
CREATE TABLE IF NOT EXISTS `feedback_intelligence.dim_channel` (
  channel_id    STRING    NOT NULL  OPTIONS (description = 'Unique channel identifier'),
  channel_name  STRING    NOT NULL  OPTIONS (description = 'Display name of the channel'),
  channel_type  STRING    NOT NULL  OPTIONS (description = 'Type: app_review, web_form, email, support_ticket, social_media'),
  is_active     BOOL                OPTIONS (description = 'Whether the channel is currently active'),
  created_at    TIMESTAMP           OPTIONS (description = 'When this channel was onboarded')
)
OPTIONS (
  description = 'Channel dimension table for feedback sources'
);

-- =============================================================================
-- Dimension Table: dim_product
-- =============================================================================
CREATE TABLE IF NOT EXISTS `feedback_intelligence.dim_product` (
  product_id       STRING    NOT NULL  OPTIONS (description = 'Unique product identifier'),
  product_name     STRING    NOT NULL  OPTIONS (description = 'Display name of the product'),
  product_category STRING              OPTIONS (description = 'Product category (e.g., SaaS, Mobile, Hardware)'),
  product_line     STRING              OPTIONS (description = 'Product line or family'),
  launch_date      DATE                OPTIONS (description = 'Date the product was launched'),
  is_active        BOOL                OPTIONS (description = 'Whether the product is currently active'),
  updated_at       TIMESTAMP           OPTIONS (description = 'Last update timestamp for this dimension record')
)
OPTIONS (
  description = 'Product dimension table'
);
