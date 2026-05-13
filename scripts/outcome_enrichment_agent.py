"""
Outcome Enrichment Agent.

Closes the feedback loop the weekly reweight depends on. Reads (mock) AE inbox
replies, classifies them, and updates data/outcomes.json with the resolved
outcome and timestamp. Without this, outcomes stay null and the reweight
proposal returns "insufficient data" forever.

Architecture:
  Reads data/sample_inbox.json (mock AE inbox in this repo; in production
  swap for the Gmail/HubSpot Engagements API). For each unread reply:
    1. Match the reply to a routed action via account_id + thread context
    2. Classify the reply text with Claude into one of:
       replied | meeting_booked | opp_created | not_relevant |
       wrong_contact | objection | no_response
    3. Update the corresponding outcomes.json entry

Usage:
  python scripts/outcome_enrichment_agent.py --dry-run
  python scripts/outcome_enrichment_agent.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

OUTCOME_LABELS = ["replied", "meeting_booked", "opp_created", "not_relevant", "wrong_contact", "objection", "no_response"]

CLASSIFIER_SYSTEM = (
    "You are an outbound reply classifier for a B2B GTM team. Return strict JSON only — no preamble, no commentary."
)

CLASSIFIER_USER_TMPL = """Reply text:
\"\"\"
{reply_text}
\"\"\"

Classify into exactly one label from this list:
- replied: prospect engaged but did not commit to next step
- meeting_booked: prospect agreed to a meeting or proposed a time
- opp_created: prospect indicated active evaluation, budget, or RFP context
- not_relevant: prospect or their org isn't a fit for this signal
- wrong_contact: should be routed to someone else
- objection: explicit objection (price, timing, vendor lock-in)
- no_response: out-of-office or other auto-reply

Return JSON:
{{"label": "<one of the above>", "rationale": "one short sentence", "next_action": "one short sentence on what the AE should do next"}}"""


def classify_reply_dry(text: str) -> dict:
    """Deterministic stub for dry-run."""
    t = (text or "").lower()
    if "out of office" in t or "ooo" in t:
        return {"label": "no_response", "rationale": "Auto-reply (OOO).", "next_action": "Re-touch in 1 week."}
    if "meeting" in t or "calendar" in t or "30 min" in t or "let's set up" in t:
        return {"label": "meeting_booked", "rationale": "Prospect proposed time or agreed to meet.", "next_action": "Send calendar invite within 24h."}
    if "rfp" in t or "evaluating" in t or "budget" in t or "vendor list" in t:
        return {"label": "opp_created", "rationale": "Prospect referenced active buying motion.", "next_action": "Loop in CSM and tag opp in CRM."}
    if "not the right person" in t or "forward" in t or "you should talk to" in t:
        return {"label": "wrong_contact", "rationale": "Reply names a different stakeholder.", "next_action": "Ask for a warm intro to the named contact."}
    if "no thanks" in t or "not interested" in t or "remove me" in t:
        return {"label": "objection", "rationale": "Explicit decline.", "next_action": "Suppress for 90d, no follow-up."}
    if "not relevant" in t or "doesn't apply" in t:
        return {"label": "not_relevant", "rationale": "Prospect indicates no exposure.", "next_action": "Mark account-vertical for suppression."}
    if any(w in t for w in ["thanks", "interesting", "tell me more", "send over", "share"]):
        return {"label": "replied", "rationale": "Engaged but no next step yet.", "next_action": "Send the requested asset and propose a 15-min call."}
    return {"label": "no_response", "rationale": "Reply text did not match a clear pattern.", "next_action": "Re-touch in 1 week with a different angle."}


def classify_reply_live(client, text: str) -> tuple[dict, dict]:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=CLASSIFIER_SYSTEM,
        messages=[{"role": "user", "content": CLASSIFIER_USER_TMPL.format(reply_text=text)}],
    )
    text_out = msg.content[0].text.strip()
    try:
        parsed = json.loads(text_out)
    except json.JSONDecodeError:
        parsed = {"label": "no_response", "rationale": "classifier returned non-JSON", "next_action": "manual review"}
    return parsed, {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    inbox_path = DATA / "sample_inbox.json"
    if not inbox_path.exists():
        print(f"missing {inbox_path}; run scripts/seed_inbox.py first", file=sys.stderr)
        return 2

    inbox = json.loads(inbox_path.read_text())
    outcomes_path = DATA / "outcomes.json"
    outcomes = json.loads(outcomes_path.read_text())
    outcomes_by_pair = {(o["bill_id"], o["account_id"]): o for o in outcomes}

    client = None
    if not args.dry_run:
        ak = os.environ.get("ANTHROPIC_API_KEY")
        if not ak:
            print("set ANTHROPIC_API_KEY or use --dry-run", file=sys.stderr)
            return 2
        from anthropic import Anthropic
        client = Anthropic(api_key=ak)

    enriched_count = 0
    usage = {"input_tokens": 0, "output_tokens": 0}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for reply in inbox:
        key = (reply["bill_id"], reply["account_id"])
        if key not in outcomes_by_pair:
            print(f"skip: no routed action for {key}", file=sys.stderr)
            continue
        if outcomes_by_pair[key].get("outcome"):
            continue  # already enriched

        if args.dry_run:
            cls = classify_reply_dry(reply["body"])
        else:
            cls, u = classify_reply_live(client, reply["body"])
            usage["input_tokens"] += u["input_tokens"]
            usage["output_tokens"] += u["output_tokens"]

        outcomes_by_pair[key]["outcome"] = cls["label"]
        outcomes_by_pair[key]["outcome_logged_at"] = now
        outcomes_by_pair[key]["enrichment"] = {
            "rationale": cls["rationale"],
            "next_action": cls["next_action"],
            "from_reply_id": reply["id"],
        }
        enriched_count += 1

    outcomes_path.write_text(json.dumps(list(outcomes_by_pair.values()), indent=2))
    print(json.dumps({"enriched": enriched_count, "claude_usage": usage, "mode": "dry-run" if args.dry_run else "live"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
