"""
Seed mock data for dry-run demos.

Subcommands:
  outcomes  — regenerate data/sample_outcomes.json (120 entries, 30-day window)
  inbox     — regenerate data/sample_inbox.json (mock AE replies tied to outcomes)

Usage:
  python scripts/seed_data.py outcomes
  python scripts/seed_data.py inbox
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


# ---------- outcomes ----------

OUTCOME_SEED = 42
OUTCOME_ACCOUNTS = [f"acc_{i:03d}" for i in range(1, 61)]
OUTCOME_ACTIONS = ["hubspot_task", "sequence_enroll", "slack_alert"]


def gen_outcomes(n: int = 120) -> list[dict]:
    random.seed(OUTCOME_SEED)
    now = datetime.now(timezone.utc)
    entries = []
    for i in range(n):
        days_ago = random.randint(0, 29)
        ts = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat(timespec="seconds")
        action = random.choices(OUTCOME_ACTIONS, weights=[0.45, 0.45, 0.10])[0]
        score = round(random.uniform(0.6, 0.97), 3)
        # Higher scores convert better; bias the outcome distribution accordingly.
        if score >= 0.85:
            outcome = random.choices(["replied", "meeting_booked", "opp_created", "no_response", None],
                                      weights=[0.25, 0.18, 0.10, 0.30, 0.17])[0]
        elif score >= 0.75:
            outcome = random.choices(["replied", "meeting_booked", "no_response", None],
                                      weights=[0.18, 0.07, 0.40, 0.35])[0]
        else:
            outcome = random.choices(["replied", "no_response", None],
                                      weights=[0.08, 0.50, 0.42])[0]
        entries.append({
            "timestamp": ts,
            "bill_id": f"ocd-bill/sample-{i:04d}",
            "account_id": random.choice(OUTCOME_ACCOUNTS),
            "score": score,
            "action_taken": action,
            "outcome": outcome,
            "outcome_logged_at": ts if outcome else None,
        })
    entries.sort(key=lambda e: e["timestamp"])
    return entries


# ---------- inbox ----------

INBOX_SEED = 2026

REPLY_TEMPLATES = {
    "meeting_booked": [
        "Thanks, this is interesting. Let's set up 30 min next Tuesday at 2pm ET.",
        "Yes, send a calendar invite, I want to walk through this with our compliance team.",
    ],
    "opp_created": [
        "Good timing, we're actively evaluating vendors for this. Can you send over your overview deck?",
        "We're putting an RFP together for Q3 covering this exact area. What's your typical engagement model?",
    ],
    "replied": [
        "Thanks for flagging. Tell me more about how you tracked this in real time.",
        "Interesting framing. Send over what you have and I'll loop in the right person internally.",
    ],
    "not_relevant": [
        "We don't operate in that state in any meaningful way, not relevant to our team.",
        "Thanks but this doesn't apply to our line of business.",
    ],
    "wrong_contact": [
        "Not the right person here, you should talk to Maya in our policy ops team. I'll forward.",
        "Forwarding this to our regulatory affairs lead, she owns this area.",
    ],
    "objection": [
        "We already have a vendor for this. No thanks.",
        "Please remove me from this list. We're not in market.",
    ],
    "no_response": [
        "I'm out of office until next week with limited email access.",
        "OOO through Friday, for urgent matters contact my assistant.",
    ],
}


def gen_inbox() -> list[dict]:
    random.seed(INBOX_SEED)
    outcomes_path = DATA / "outcomes.json"
    if not outcomes_path.exists():
        raise FileNotFoundError(
            f"{outcomes_path} not found; the inbox seeder is keyed off real routed actions. "
            "Run scripts/run_pipeline.py (or the previous run) to populate outcomes.json first."
        )
    outcomes = json.loads(outcomes_path.read_text())
    inbox = []
    now = datetime.now(timezone.utc)

    # ~50% reply rate, biased toward higher-score actions getting better outcomes
    for i, o in enumerate(outcomes):
        if random.random() > 0.5:
            continue  # no reply

        score = o.get("score", 0.7)
        if score >= 0.9:
            label_weights = [("meeting_booked", 0.20), ("opp_created", 0.10), ("replied", 0.30),
                             ("not_relevant", 0.05), ("wrong_contact", 0.10), ("objection", 0.05),
                             ("no_response", 0.20)]
        elif score >= 0.8:
            label_weights = [("meeting_booked", 0.10), ("opp_created", 0.05), ("replied", 0.30),
                             ("not_relevant", 0.10), ("wrong_contact", 0.10), ("objection", 0.10),
                             ("no_response", 0.25)]
        else:
            label_weights = [("meeting_booked", 0.05), ("opp_created", 0.02), ("replied", 0.20),
                             ("not_relevant", 0.20), ("wrong_contact", 0.08), ("objection", 0.15),
                             ("no_response", 0.30)]

        labels, weights = zip(*label_weights)
        chosen = random.choices(labels, weights=weights)[0]
        body = random.choice(REPLY_TEMPLATES[chosen])

        inbox.append({
            "id": f"reply_{i:04d}",
            "received_at": (now - timedelta(hours=random.randint(1, 72))).isoformat(timespec="seconds"),
            "from_email": f"contact@{o['account_id']}.example",
            "to_ae": o.get("owner_ae", "ae_unknown"),
            "subject": f"Re: [Policy Signal] {o.get('bill_identifier','')}",
            "bill_id": o["bill_id"],
            "account_id": o["account_id"],
            "body": body,
            "true_label_for_eval": chosen,
        })

    return inbox


# ---------- entry ----------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=["outcomes", "inbox"])
    args = p.parse_args()

    if args.kind == "outcomes":
        path = DATA / "sample_outcomes.json"
        rows = gen_outcomes()
        path.write_text(json.dumps(rows, indent=2))
        print(f"wrote {path} with {len(rows)} entries")
    elif args.kind == "inbox":
        path = DATA / "sample_inbox.json"
        rows = gen_inbox()
        path.write_text(json.dumps(rows, indent=2))
        print(f"wrote {path} with {len(rows)} simulated replies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
