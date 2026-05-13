# Weekly reweight proposal (human-in-loop)

Used by `scripts/weekly_reweight.py`. Reads the last 30 days of `outcomes.json`, asks Claude to identify the single weight most worth nudging, and writes a JSON proposal.

This is a *proposal*, not an auto-apply. The output goes to `outputs/reweight_proposal.json` and a human RevOps analyst reviews it before any change to `scoring_config.yaml` is merged.

Why human-in-loop:
1. Weight tuning at small N (a few weeks of outcomes) is noisy. LLM judgment is no replacement for a logistic regression once data scales, but it's a fine first pass when you have 50 outcomes, not 50,000.
2. A human approval step prevents drift loops where one bad week silently rewrites the config.

The script enforces a hard cap of ±0.05 per cycle and falls back to "insufficient data" below 20 positive outcomes.

## Model
`claude-sonnet-4-6` — runs weekly, no need for Opus.

## Production strings

The strings below are the source of truth. `scripts/_lib/prompts.py` loads them at runtime.

```system
You are a RevOps analyst proposing scoring weight adjustments based on outcome data. Return strict JSON only.
```

```user
Current weights: {weights}
Outcomes from the last 30 days (action_taken, score, outcome):
{outcomes_csv}

Identify the single weight (if any) that should be adjusted up or down by no more than 0.05, based on which factor most differentiates positive outcomes from null or negative ones.

Return JSON:
{{"adjustment": {{"weight_name": delta}}, "rationale": "one sentence"}}

If positive outcomes n < 20 in the period, return:
{{"adjustment": {{}}, "rationale": "insufficient data"}}
```
