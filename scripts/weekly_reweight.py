"""
Weekly re-weight proposal (human-in-loop).

Reads outcomes.json from the last 30 days, asks Claude to propose at most a
±0.05 adjustment to one weight, and writes outputs/reweight_proposal.json
for a human RevOps analyst to review before merging into scoring_config.yaml.

Usage:
  python scripts/weekly_reweight.py                  # live, requires ANTHROPIC_API_KEY
  python scripts/weekly_reweight.py --dry-run        # uses data/sample_outcomes.json + canned response
  python scripts/weekly_reweight.py --vertical insurance  # default; one vertical at a time
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import prompts

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)


def _csv_outcomes(outcomes: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["action_taken", "score", "outcome"])
    for o in outcomes:
        w.writerow([o.get("action_taken", ""), o.get("score", ""), o.get("outcome") or "null"])
    return buf.getvalue()


def _filter_recent(outcomes: list[dict], days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for o in outcomes:
        ts = o.get("timestamp")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if t >= cutoff:
            out.append(o)
    return out


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    s = sum(weights.values())
    if s == 0:
        return weights
    return {k: round(v / s, 4) for k, v in weights.items()}


def apply_proposal(weights: dict[str, float], proposal: dict) -> dict[str, float]:
    adj = proposal.get("adjustment", {})
    if not adj:
        return weights
    new = dict(weights)
    for k, delta in adj.items():
        if k not in new:
            continue
        delta = max(-0.05, min(0.05, float(delta)))
        new[k] = round(new[k] + delta, 4)
    return normalize_weights(new)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vertical", default="insurance")
    p.add_argument("--days", type=int, default=30)
    args = p.parse_args()

    cfg = yaml.safe_load((DATA / "scoring_config.yaml").read_text())
    if args.vertical not in cfg["verticals"]:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    weights = cfg["verticals"][args.vertical]["weights"]

    outcomes_path = DATA / ("sample_outcomes.json" if args.dry_run else "outcomes.json")
    if not outcomes_path.exists():
        print(f"missing {outcomes_path}", file=sys.stderr)
        return 2
    outcomes = json.loads(outcomes_path.read_text())
    recent = _filter_recent(outcomes, args.days)
    positive_n = sum(1 for o in recent if o.get("outcome") in {"replied", "meeting_booked", "opp_created"})

    proposal: dict
    if positive_n < 20:
        proposal = {"adjustment": {}, "rationale": "insufficient data"}
        usage = {"input_tokens": 0, "output_tokens": 0}
    elif args.dry_run:
        proposal = {
            "adjustment": {"urgency": 0.03},
            "rationale": "Higher-urgency signals converted at 2.4x the rate of mid-urgency in the sample period; nudging urgency weight up.",
        }
        usage = {"input_tokens": 0, "output_tokens": 0}
    else:
        ak = os.environ.get("ANTHROPIC_API_KEY")
        if not ak:
            print("set ANTHROPIC_API_KEY or use --dry-run", file=sys.stderr)
            return 2
        client = Anthropic(api_key=ak)
        system, user_tmpl = prompts.load("reweight")
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user_tmpl.format(
                weights=json.dumps(weights), outcomes_csv=_csv_outcomes(recent)
            )}],
        )
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        proposal = json.loads(msg.content[0].text.strip())

    proposed_weights = apply_proposal(weights, proposal)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vertical": args.vertical,
        "window_days": args.days,
        "outcomes_in_window": len(recent),
        "positive_outcomes": positive_n,
        "current_weights": weights,
        "proposed_weights": proposed_weights,
        "proposal": proposal,
        "claude_usage": usage,
        "status": "PENDING_HUMAN_REVIEW",
        "review_note": "Edit data/scoring_config.yaml manually if approved. This file is informational only.",
    }
    (OUTPUTS / "reweight_proposal.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
