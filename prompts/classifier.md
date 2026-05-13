# Prompt 1 — Bill classifier

Used in the n8n classification node and in `scripts/run_pipeline.py`. Produces structured tags, urgency, topic summary, and exposed entity types from a raw bill record.

## Model
`claude-sonnet-4-6` — fast, cheap, good enough for structured tagging at this scale.

## System

You are a policy analyst classifying state legislation for a B2B GTM team. Return strict JSON only — no preamble, no commentary, no markdown fences.

## User

```
Bill: {identifier} — {title}
State: {state}
Subjects: {subjects}
Latest action ({latest_action_date}): {latest_action}

Classify. Return JSON with exactly these fields:

industries: array of tags from this controlled list:
["healthcare", "insurance", "financial_services", "tech", "retail",
 "food_service", "energy", "manufacturing", "transportation",
 "education", "agriculture", "telecom", "real_estate",
 "advocacy_seniors", "advocacy_consumer"]

urgency: integer 1-5
  5 = floor vote or signing imminent
  4 = committee action this week
  3 = active in committee
  2 = introduced and assigned
  1 = dormant

topic_summary: one sentence, max 25 words, naming the regulatory mechanism.

affected_entities: array of 2-4 short phrases naming the company types most exposed.
```

## Notes

- `industries` is a closed vocabulary so downstream matching against `account.industry` is deterministic.
- `urgency` is inferred from `latest_action` text (e.g., "Read third time", "Passed Senate", "Signed by Governor" → 5). The model handles language variation across states.
- `affected_entities` is for human readability in the briefing, not used for matching.
- Cost at sample scale: ~50 bills/day × Sonnet input ~400 tokens, output ~150 tokens ≈ $0.005/day.
