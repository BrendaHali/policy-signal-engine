"""
Generate a realistic mock AE inbox tied to the routed actions in outcomes.json.

Output: data/sample_inbox.json — one entry per simulated reply, keyed by
(bill_id, account_id) so the outcome enrichment agent can pair them.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

random.seed(2026)

REPLY_TEMPLATES = [
    ("meeting_booked", [
        "Thanks, this is interesting. Let's set up 30 min next Tuesday at 2pm ET.",
        "Yes, send a calendar invite — I want to walk through this with our compliance team.",
    ]),
    ("opp_created", [
        "Good timing — we're actively evaluating vendors for this. Can you send over your overview deck?",
        "We're putting an RFP together for Q3 covering this exact area. What's your typical engagement model?",
    ]),
    ("replied", [
        "Thanks for flagging. Tell me more about how you tracked this in real time.",
        "Interesting framing. Send over what you have and I'll loop in the right person internally.",
    ]),
    ("not_relevant", [
        "We don't operate in that state in any meaningful way — not relevant to our team.",
        "Thanks but this doesn't apply to our line of business.",
    ]),
    ("wrong_contact", [
        "Not the right person here — you should talk to Maya in our policy ops team. I'll forward.",
        "Forwarding this to our regulatory affairs lead, she owns this area.",
    ]),
    ("objection", [
        "We already have a vendor for this. No thanks.",
        "Please remove me from this list. We're not in market.",
    ]),
    ("no_response", [
        "I'm out of office until next week with limited email access.",
        "OOO through Friday — for urgent matters contact my assistant.",
    ]),
]


def gen() -> list[dict]:
    outcomes = json.loads((DATA / "outcomes.json").read_text())
    inbox = []
    now = datetime.now(timezone.utc)

    # ~50% reply rate, biased toward higher-score actions getting better outcomes
    for i, o in enumerate(outcomes):
        roll = random.random()
        if roll > 0.5:
            continue  # no reply

        score = o.get("score", 0.7)
        # higher score skews toward better outcomes
        if score >= 0.9:
            label_weights = [("meeting_booked", 0.20), ("opp_created", 0.10), ("replied", 0.30), ("not_relevant", 0.05), ("wrong_contact", 0.10), ("objection", 0.05), ("no_response", 0.20)]
        elif score >= 0.8:
            label_weights = [("meeting_booked", 0.10), ("opp_created", 0.05), ("replied", 0.30), ("not_relevant", 0.10), ("wrong_contact", 0.10), ("objection", 0.10), ("no_response", 0.25)]
        else:
            label_weights = [("meeting_booked", 0.05), ("opp_created", 0.02), ("replied", 0.20), ("not_relevant", 0.20), ("wrong_contact", 0.08), ("objection", 0.15), ("no_response", 0.30)]

        labels, weights = zip(*label_weights)
        chosen = random.choices(labels, weights=weights)[0]
        body = random.choice(dict(REPLY_TEMPLATES)[chosen])

        inbox.append({
            "id": f"reply_{i:04d}",
            "received_at": (now - timedelta(hours=random.randint(1, 72))).isoformat(timespec="seconds"),
            "from_email": f"contact@{o['account_id']}.example",
            "to_ae": o.get("owner_ae", "ae_unknown"),
            "subject": f"Re: [Policy Signal] {o['bill_identifier']}",
            "bill_id": o["bill_id"],
            "account_id": o["account_id"],
            "body": body,
            "true_label_for_eval": chosen,  # ground truth for testing the classifier
        })

    return inbox


if __name__ == "__main__":
    path = DATA / "sample_inbox.json"
    inbox = gen()
    path.write_text(json.dumps(inbox, indent=2))
    print(f"wrote {path} with {len(inbox)} simulated replies")
