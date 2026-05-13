-- 03_outcomes_analysis.sql
-- Closes the loop. For each routing decision, did anything happen downstream?
-- Source: `gtm.outcomes` (action_taken, score) JOIN `crm.activities` (replies, meetings, opps).
-- This is what feeds the weekly re-weight proposal — and what we'd hand a stats
-- model once we have enough rows to run logistic regression on.

WITH labeled AS (
  SELECT
    o.bill_id,
    o.account_id,
    o.score,
    o.action_taken,
    o.timestamp AS routed_at,
    -- positive = AE replied, booked a meeting, or opp created within 14 days
    MAX(CASE
      WHEN c.activity_type IN ('reply', 'meeting_booked', 'opp_created')
       AND c.activity_ts BETWEEN o.timestamp AND TIMESTAMP_ADD(o.timestamp, INTERVAL 14 DAY)
      THEN 1 ELSE 0
    END) AS positive_outcome
  FROM `gtm.outcomes` o
  LEFT JOIN `crm.activities` c
    ON c.account_id = o.account_id
   AND c.activity_ts >= o.timestamp
  WHERE o.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  GROUP BY o.bill_id, o.account_id, o.score, o.action_taken, o.timestamp
)
SELECT
  action_taken,
  -- bucket scores so we can see if the 0.6-0.7 tier is actually pulling weight
  CASE
    WHEN score >= 0.9 THEN '0.9-1.0'
    WHEN score >= 0.8 THEN '0.8-0.9'
    WHEN score >= 0.7 THEN '0.7-0.8'
    ELSE '0.6-0.7'
  END AS score_bucket,
  COUNT(*) AS routed,
  SUM(positive_outcome) AS positive,
  ROUND(SAFE_DIVIDE(SUM(positive_outcome), COUNT(*)), 3) AS positive_rate,
  ROUND(AVG(score), 3) AS avg_score
FROM labeled
GROUP BY action_taken, score_bucket
ORDER BY action_taken, score_bucket DESC;
