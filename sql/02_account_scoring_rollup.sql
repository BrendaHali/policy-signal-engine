-- 02_account_scoring_rollup.sql
-- Per-account view: which accounts had the most high-scoring signals this week,
-- by tier and engagement status. Used by AEs Monday morning.
-- Source: `gtm.bill_account_matches` — one row per (bill_id, account_id, run_date).

WITH weekly AS (
  SELECT
    account_id,
    account_name,
    industry,
    tier,
    engagement_status,
    owner_ae,
    COUNT(*) AS matches,
    COUNTIF(score >= 0.8) AS top_tier_matches,
    COUNTIF(score >= 0.6 AND score < 0.8) AS bulk_matches,
    MAX(score) AS top_score,
    ARRAY_AGG(STRUCT(bill_identifier, bill_state, score) ORDER BY score DESC LIMIT 3) AS top_3_bills
  FROM `gtm.bill_account_matches`
  WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND score >= 0.6
  GROUP BY account_id, account_name, industry, tier, engagement_status, owner_ae
)
SELECT
  owner_ae,
  account_id,
  account_name,
  industry,
  tier,
  engagement_status,
  matches,
  top_tier_matches,
  bulk_matches,
  ROUND(top_score, 3) AS top_score,
  top_3_bills
FROM weekly
ORDER BY owner_ae, tier ASC, top_tier_matches DESC, top_score DESC;
