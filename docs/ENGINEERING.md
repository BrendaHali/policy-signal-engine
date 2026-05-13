# Engineering

Reference documentation for the pipeline. README covers the strategic frame; this doc covers how the system is built.

## Stack

| Layer | Choice | Note |
|---|---|---|
| Orchestration | n8n at `workflow/bill_to_action.json` | Imports into n8n cloud free tier; fetches accounts and config from this repo's raw GitHub URLs |
| Reference engine | Python at `scripts/run_pipeline.py` | Same logic, runnable in CI or locally; used for the committed run |
| Signal source | Open States API v3 | Bills, classifications, sponsors, actions across 50 states; free tier covers steady-state usage |
| LLM | Claude (Sonnet 4.6, Opus 4.7) | Sonnet for high-volume classifier and bulk drafter, Opus for top-tier drafter, Sonnet for the agents and reweight |
| Data layer | JSON files in `data/` | Designed to swap to BigQuery or Postgres without changing pipeline shape; see `sql/` for the warehouse-side queries |
| Routing destinations | Mock HubSpot tasks, mock outbound sequences, Slack incoming webhook | One node swap each to wire to the real systems |
| Prompt source of truth | `prompts/*.md` | Python loads system + user templates via `scripts/_lib/prompts.py` so the markdown files cannot drift from production strings |

## Repo layout

```
data/
  accounts.json                60 mock accounts across 6 verticals
  scoring_config.yaml          weights, relevant_topics, urgency_floor per vertical
  outcomes.json                appended by the pipeline; enriched by the outcome agent
  sample_outcomes.json         seeded 30-day window for reweight demo
  sample_inbox.json            mock AE inbox replies for the enrichment agent
  classification_cache.json    bill_id -> classification (auto-managed)
  errors.json                  structured pipeline error log
prompts/
  classifier.md                bill -> structured classification
  drafter.md                   matched pair -> 3-part briefing
  reweight.md                  outcomes log -> weight adjustment proposal
workflow/
  bill_to_action.json          n8n workflow, 17 nodes, importable into n8n cloud
sql/
  01_signal_aggregation.sql    daily rollup by state x industry
  02_account_scoring_rollup.sql  weekly per-AE matches view
  03_outcomes_analysis.sql     positive_rate by score bucket
scripts/
  _lib/cache.py                ClassificationCache (bill_id keyed)
  _lib/errors.py               ErrorLog (structured row writer)
  _lib/prompts.py              prompt loader (parses prompts/*.md)
  run_pipeline.py              live OR dry-run end-to-end
  weekly_reweight.py           proposal-only, human approves
  account_research_agent.py    enriches top-tier matches via tool-using agent
  outcome_enrichment_agent.py  classifies AE replies, updates outcomes log
  seed_data.py                 regenerates sample outcomes and inbox (subcommands)
tests/
  test_scoring.py              16 cases, scoring + match gating + edge cases
  test_cache.py                cache hit/miss + invalidation
outputs/
  raw_bills.json               92 bills pulled live from Open States
  classified_bills.json        + Claude classification per bill
  matches.json                 383 (bill, account) pairs above threshold
  hubspot_tasks.json           15 top-tier briefings (Opus)
  sequences.json               25 bulk briefings (Sonnet)
  slack_alerts.json            15 urgency-5 alerts
  enriched_briefings.json      account research agent output for top 5 matches
  reweight_proposal.json       weekly proposal output
  run_summary.json             counts, costs, cache stats, mode
docs/
  STRATEGY.md                  positioning, ICP, hypotheses, metrics, rollout
  MOTION.md                    talk tracks, ROI model, land-and-expand, renewals
  ENGINEERING.md               this document
```

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env  # add OPENSTATES_API_KEY and ANTHROPIC_API_KEY

# end-to-end live run (uses the classification cache + error log)
python scripts/run_pipeline.py

# narrow scope while iterating
python scripts/run_pipeline.py --states ca,tx --since 7

# zero-cost demo from committed sample data, no keys needed
python scripts/run_pipeline.py --dry-run

# enrich top-5 hubspot tasks with deeper research (agent loop)
python scripts/account_research_agent.py --top-n 5

# classify AE replies and fill in the outcomes log
python scripts/outcome_enrichment_agent.py

# weekly proposal
python scripts/weekly_reweight.py

# seed mock data for dry-run demos
python scripts/seed_data.py outcomes
python scripts/seed_data.py inbox

# tests
python -m pytest tests/ -v
```

The n8n workflow is the production-shaped equivalent. Import `workflow/bill_to_action.json` into n8n cloud, set the env vars in Settings, and it runs on the same daily cron.

## How the score works

Each (bill, account) pair gates first, then scores.

**Gate:**
- Bill's classified industries intersect `account.industry` directly OR adjacently (insurance ↔ financial_services ↔ healthcare; retail ↔ food_service; energy ↔ manufacturing; telecom ↔ tech).
- `bill.state` is in `account.state_footprint`.

**Weighted score** (0-1, summed from four factors per the vertical's weights in `scoring_config.yaml`):
- `industry_match`: 1.0 direct, 0.4 adjacent
- `urgency`: `classification.urgency / 5`
- `state_footprint_overlap`: 1.0 if the gate passed
- `engagement`: prospect-hot 1.0, customer-renewal 0.9, prospect-warm 0.7, customer-active 0.6, prospect-cold 0.4, churned-recent 0.2

The pair routes only if `score >= 0.6` AND `classification.urgency >= vertical.urgency_floor`. Per-AE caps then trim to a realistic daily volume. The 16-test suite in `tests/test_scoring.py` covers the gate, the weights, the urgency floor, and adjacency.

## The two agents

**Account Research Agent** (`scripts/account_research_agent.py`)
Triggered on top-tier matches. Multi-step Claude agent using `web_search` and `fetch_url` tools. Pulls account-specific exposure context: recent press, regulatory positioning, competitor lens. Outputs an enriched briefing with structured evidence and confidence scoring. In dry-run mode the tools return deterministic stubs so the agent can demo without external dependencies. To go live, swap the tool implementations for Tavily/SerpAPI/Bing.

**Outcome Enrichment Agent** (`scripts/outcome_enrichment_agent.py`)
Reads the AE inbox (mock here, Gmail/HubSpot Engagements API in production), classifies each reply into one of seven labels (replied, meeting_booked, opp_created, not_relevant, wrong_contact, objection, no_response), and writes the resolved outcome back to `data/outcomes.json`. Without this, the outcomes log stays null and the reweight proposal returns "insufficient data" forever. The dry-run classifier matches the live Claude classifier's output shape so the rest of the system is invariant to mode.

## Closing the loop: the reweight proposal

`scripts/weekly_reweight.py` reads the last 30 days of `outcomes.json`, asks Claude to identify the single weight (max +/- 0.05) most worth nudging based on which factor most differentiates positive outcomes from null or negative ones, and writes `outputs/reweight_proposal.json` for a human RevOps analyst to review.

This is deliberately a proposal, not auto-apply. At small N the LLM judgment is a useful first pass. At larger N this hands off to a logistic regression. The human approval step prevents drift loops and keeps an analyst in the change path. Framing in `prompts/reweight.md`.

## Robustness

The pipeline ships with three production-grade pieces beyond the core flow.

**Classification cache** (`scripts/_lib/cache.py`)
Bill-id keyed, invalidated on `latest_action_date` change. Cuts steady-state Sonnet classifier calls by an estimated 70% (only re-classify bills that have moved since the last run). Persists as JSON; swap for Redis or KV in production.

**Error log** (`scripts/_lib/errors.py`)
Structured rows to `data/errors.json`. Each entry: timestamp, stage, level, context, exception type, message, three-line traceback. Wired into fetch and classify; extends trivially to draft and route.

**Test suite** (`tests/`)
16 cases covering scoring (gate, weights, urgency floor, adjacency, engagement), match gating, and cache hit/miss/invalidation. Pure-logic tests, no external deps. Runs in 0.25s.

## Cost

At the run scope shipped here:

- Open States: free tier (500 daily requests, 1 req/sec); pipeline uses ~30
- Claude classifier (Sonnet 4.6): ~92 bills × 400 in / 150 out tokens = ~$0.32
- Claude drafter (Opus 4.7) for top-tier: ~15 briefings × 300 in / 150 out = ~$0.05
- Claude drafter (Sonnet 4.6) for bulk + slack: ~40 briefings × 250 in / 100 out = ~$0.04
- Account Research Agent: ~5 runs × 2-3 tool turns × 800 in / 300 out = ~$0.10
- Outcome Enrichment Agent: ~22 reply classifications × 200 in / 80 out = ~$0.02
- Reweight proposal: ~1 call × 600 in / 200 out = ~$0.005
- Total per daily run: under $0.55 on first run, drops to ~$0.20 in steady state with the cache on
