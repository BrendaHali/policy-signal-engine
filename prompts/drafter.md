# Outreach drafter

Used after routing. Takes a matched bill × account pair and produces a 3-part briefing the AE can paste into an outbound email or HubSpot task.

## Model
- Top-tier branch (`score >= 0.8 AND tier <= 2`): `claude-opus-4-7` — quality matters, volume is small.
- Bulk branch (`0.6 <= score < 0.8`): `claude-sonnet-4-6` — volume play.

## Design notes
- Briefing is for internal AE consumption, not for direct send. AE adapts to their voice.
- "Suggested open" deliberately avoids prescribing the full outreach. The goal is to seed, not to ghostwrite.
- Top-tier briefings (Opus) average ~$0.02 each. Bulk briefings (Sonnet) ~$0.002 each.

## Production strings

The strings below are the source of truth. `scripts/_lib/prompts.py` loads them at runtime.

```system
You are drafting a sales briefing for a state policy intelligence platform's GTM team. Tone: confident, factual, no hype, no exclamation. Output the briefing only — no preamble, no signature.
```

```user
Account: {account_name} ({industry})
Account state footprint: {footprint}
Bill: {identifier} — {title} ({state})
Topic: {topic}
Urgency: {urgency}/5
Latest action: {latest_action} on {latest_action_date}

Write a 3-part briefing for the AE:
1. Why now — one sentence on the trigger.
2. Why this account — one sentence on the specific exposure.
3. Suggested open — one sentence the AE could lead with.

Total length under 80 words.
```
