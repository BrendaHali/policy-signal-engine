"""
Generate a realistic outcomes log for the reweight demo.

Produces data/sample_outcomes.json with 60 entries spread over the past 30 days,
mixing action types and outcomes (positive / null / negative) so the reweight
script has signal to work with.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

random.seed(42)

ACCOUNTS = [f"acc_{i:03d}" for i in range(1, 61)]
ACTIONS = ["hubspot_task", "sequence_enroll", "slack_alert"]
OUTCOMES_POOL = ["replied", "meeting_booked", "opp_created", None, None, None, "no_response", "no_response"]


def gen() -> list[dict]:
    now = datetime.now(timezone.utc)
    entries = []
    for i in range(120):
        days_ago = random.randint(0, 29)
        ts = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat(timespec="seconds")
        action = random.choices(ACTIONS, weights=[0.45, 0.45, 0.10])[0]
        score = round(random.uniform(0.6, 0.97), 3)
        # higher scores convert better — bias the outcome distribution
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
            "account_id": random.choice(ACCOUNTS),
            "score": score,
            "action_taken": action,
            "outcome": outcome,
            "outcome_logged_at": ts if outcome else None,
        })
    entries.sort(key=lambda e: e["timestamp"])
    return entries


if __name__ == "__main__":
    path = DATA / "sample_outcomes.json"
    path.write_text(json.dumps(gen(), indent=2))
    print(f"wrote {path}")
