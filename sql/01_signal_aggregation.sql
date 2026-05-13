-- 01_signal_aggregation.sql
-- Daily rollup of inbound bill signals by state and classified industry.
-- Source table assumed: `gtm.bills_classified` — one row per (bill_id, ingest_date).
-- Use case: morning dashboard for the GTM team. Where is the policy heat today?

WITH daily_signals AS (
  SELECT
    DATE(ingest_ts) AS signal_date,
    state,
    industry,
    COUNTIF(urgency >= 4) AS high_urgency_count,
    COUNTIF(urgency = 5) AS imminent_count,
    COUNT(*) AS total_signals,
    AVG(urgency) AS avg_urgency
  FROM `gtm.bills_classified`,
    UNNEST(classification.industries) AS industry
  WHERE ingest_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY signal_date, state, industry
)
SELECT
  signal_date,
  state,
  industry,
  total_signals,
  high_urgency_count,
  imminent_count,
  ROUND(avg_urgency, 2) AS avg_urgency,
  -- 7-day rolling baseline so we can spot today's spikes
  AVG(total_signals) OVER (
    PARTITION BY state, industry
    ORDER BY UNIX_DATE(signal_date)
    RANGE BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS signals_7d_avg
FROM daily_signals
ORDER BY signal_date DESC, high_urgency_count DESC, total_signals DESC;
