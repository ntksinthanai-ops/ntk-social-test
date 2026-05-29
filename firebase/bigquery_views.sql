-- BigQuery SQL views to power Grafana Dashboards
-- Data is exported from Firestore to BigQuery under the 'firestore_export' dataset in the 'ntk-social' project.

-- 1. Executive KPIs View
CREATE OR REPLACE VIEW `ntk-social.ntk_dashboard.vw_executive_kpis` AS
SELECT 
  c.platform,
  COUNT(DISTINCT c.content_id) AS total_posts,
  SUM(m.video_views) AS total_views,
  SUM(m.engagement) AS total_engagement
FROM `ntk-social.firestore_export.content_items` c
LEFT JOIN `ntk-social.firestore_export.content_metrics_daily` m ON c.content_id = m.content_id
GROUP BY c.platform;

-- 2. Monthly Reach Trend View
CREATE OR REPLACE VIEW `ntk-social.ntk_dashboard.vw_monthly_reach_trend` AS
SELECT 
  platform,
  DATE_TRUNC(published_at, MONTH) AS month,
  SUM(reach) AS total_reach
FROM `ntk-social.firestore_export.content_items` c
LEFT JOIN `ntk-social.firestore_export.content_metrics_daily` m ON c.content_id = m.content_id
GROUP BY platform, month;

-- 3. Platform Comparison View
CREATE OR REPLACE VIEW `ntk-social.ntk_dashboard.vw_platform_comparison` AS
SELECT 
  platform,
  SUM(engagement) AS total_engagement,
  SUM(reach) AS total_reach,
  SAFE_DIVIDE(SUM(engagement), SUM(reach)) * 100 AS engagement_rate
FROM `ntk-social.firestore_export.content_metrics_daily` m
JOIN `ntk-social.firestore_export.content_items` c ON m.content_id = c.content_id
GROUP BY platform;

-- 4. Audience Demographics View
CREATE OR REPLACE VIEW `ntk-social.ntk_dashboard.vw_audience_demographics` AS
SELECT 
  account_id,
  dim_type,
  dim_value,
  SUM(value) AS metric_value
FROM `ntk-social.firestore_export.audience_dimensions`
GROUP BY account_id, dim_type, dim_value;

-- 5. Content Performance View
CREATE OR REPLACE VIEW `ntk-social.ntk_dashboard.vw_content_performance` AS
SELECT 
  c.content_id,
  c.platform,
  c.caption,
  c.published_at,
  SUM(m.engagement) AS engagement,
  SUM(m.reach) AS reach,
  RANK() OVER (PARTITION BY c.platform ORDER BY SUM(m.engagement) DESC) AS rank
FROM `ntk-social.firestore_export.content_items` c
JOIN `ntk-social.firestore_export.content_metrics_daily` m ON c.content_id = m.content_id
GROUP BY c.content_id, c.platform, c.caption, c.published_at;

-- 6. Sentiment Summary View
CREATE OR REPLACE VIEW `ntk-social.ntk_dashboard.vw_sentiment_summary` AS
SELECT 
  sentiment,
  stance,
  target,
  COUNT(*) AS comment_count,
  COUNTIF(reviewed = false) AS pending_review_count
FROM `ntk-social.firestore_export.comment_sentiment`
GROUP BY sentiment, stance, target;
