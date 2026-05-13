"""
End-to-end pipeline: Open States -> Claude classifier -> score -> route -> log.

Usage:
  python scripts/run_pipeline.py                  # live mode, requires keys
  python scripts/run_pipeline.py --dry-run        # uses data/sample_raw_bills.json
  python scripts/run_pipeline.py --states ca,tx   # override default state set
  python scripts/run_pipeline.py --since 7        # days back, default 1

Env vars (live mode):
  OPENSTATES_API_KEY   from https://openstates.org/accounts/profile/
  ANTHROPIC_API_KEY    from https://console.anthropic.com/

Outputs (written to outputs/):
  raw_bills.json           normalized Open States response
  classified_bills.json    + Claude classification per bill
  matches.json             scored bill x account pairs above threshold
  hubspot_tasks.json       routed top-tier briefings (Opus drafted)
  sequences.json           routed bulk briefings (Sonnet drafted)
  slack_alerts.json        routed urgency=5 alerts
  run_summary.json         counts, costs, errors
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml
from anthropic import Anthropic

from _lib.cache import ClassificationCache
from _lib.errors import ErrorLog

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)

CACHE_PATH = DATA / "classification_cache.json"
ERROR_PATH = DATA / "errors.json"

DEFAULT_STATES = ["ca", "tx", "fl", "ny", "pa", "il", "oh", "ga", "nc", "mi"]
OPENSTATES_BASE = "https://v3.openstates.org"

ENGAGEMENT_SCORES = {
    "prospect-hot": 1.0,
    "customer-renewal": 0.9,
    "prospect-warm": 0.7,
    "customer-active": 0.6,
    "prospect-cold": 0.4,
    "churned-recent": 0.2,
}

ADJACENT_INDUSTRIES = {
    "insurance": {"financial_services", "healthcare"},
    "financial_services": {"insurance"},
    "healthcare": {"insurance"},
    "retail": {"food_service"},
    "energy": {"manufacturing"},
    "telecom": {"tech"},
}


# ---------- data layer ----------

def load_accounts() -> list[dict[str, Any]]:
    return json.loads((DATA / "accounts.json").read_text())


def load_scoring_config() -> dict[str, Any]:
    return yaml.safe_load((DATA / "scoring_config.yaml").read_text())


# ---------- step 1: fetch ----------

def fetch_openstates_bills(api_key: str, states: list[str], since_days: int) -> list[dict[str, Any]]:
    """Pull bills updated in the last N days across the given states."""
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
    out = []
    headers = {"X-API-KEY": api_key}
    with httpx.Client(timeout=30.0) as client:
        for st in states:
            page = 1
            while True:
                params = {
                    "jurisdiction": st,
                    "sort": "updated_desc",
                    "updated_since": since,
                    "per_page": 20,
                    "page": page,
                    "include": ["subjects"],
                }
                r = client.get(f"{OPENSTATES_BASE}/bills", params=params, headers=headers)
                if r.status_code == 429:
                    time.sleep(2.0)
                    continue
                r.raise_for_status()
                body = r.json()
                results = body.get("results", [])
                out.extend(_normalize_bill(b) for b in results)
                if len(results) < 20 or page >= 3:  # cap at 60/state for demo
                    break
                page += 1
                time.sleep(0.3)  # be nice to the API
    return out


def _normalize_bill(raw: dict[str, Any]) -> dict[str, Any]:
    latest = raw.get("latest_action_description") or ""
    latest_date = raw.get("latest_action_date") or ""
    return {
        "id": raw.get("id"),
        "state": raw.get("jurisdiction", {}).get("name", "").lower()[:2] if isinstance(raw.get("jurisdiction"), dict) else raw.get("jurisdiction", "").lower()[:2],
        "session": raw.get("session"),
        "identifier": raw.get("identifier"),
        "title": raw.get("title", "")[:500],
        "latest_action_date": latest_date,
        "latest_action": latest,
        "subjects": raw.get("subjects", []),
        "url": raw.get("openstates_url"),
    }


# ---------- step 2: classify ----------

CLASSIFIER_SYSTEM = (
    "You are a policy analyst classifying state legislation for a B2B GTM team. "
    "Return strict JSON only — no preamble, no commentary, no markdown fences."
)

CLASSIFIER_USER_TMPL = """Bill: {identifier} — {title}
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

affected_entities: array of 2-4 short phrases naming the company types most exposed."""


def classify_bills(
    client: Anthropic,
    bills: list[dict[str, Any]],
    cache: ClassificationCache | None = None,
    errors: ErrorLog | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """Classify bills with cache + error logging.

    Returns (bills, claude_usage, cache_stats). Cache hits skip the API call
    when latest_action_date matches the cached value.
    """
    out = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    cache_stats = {"hits": 0, "misses": 0}

    for b in bills:
        cached = cache.get(b["id"], b.get("latest_action_date")) if cache else None
        if cached is not None:
            b["classification"] = cached
            out.append(b)
            cache_stats["hits"] += 1
            continue

        cache_stats["misses"] += 1
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=CLASSIFIER_SYSTEM,
                messages=[{"role": "user", "content": CLASSIFIER_USER_TMPL.format(
                    identifier=b["identifier"], title=b["title"], state=b["state"],
                    subjects=", ".join(b["subjects"][:8]) or "none",
                    latest_action_date=b["latest_action_date"], latest_action=b["latest_action"]
                )}],
            )
            usage["input_tokens"] += msg.usage.input_tokens
            usage["output_tokens"] += msg.usage.output_tokens
            text = msg.content[0].text.strip()
            classification = json.loads(text)
            b["classification"] = classification
            if cache:
                cache.put(b["id"], b.get("latest_action_date"), classification)
        except Exception as e:
            b["classification"] = None
            if errors:
                errors.error("classify", e, context={"bill_id": b.get("id"), "identifier": b.get("identifier"), "state": b.get("state")})
        out.append(b)

    return out, usage, cache_stats


# ---------- step 3: match & score ----------

@dataclass
class Match:
    bill: dict[str, Any]
    account: dict[str, Any]
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)


def score_pair(bill: dict[str, Any], account: dict[str, Any], cfg: dict[str, Any]) -> Match | None:
    cls = bill.get("classification") or {}
    industries = set(cls.get("industries", []))
    if not industries:
        return None

    vertical = cfg["verticals"].get(account["vertical_config"])
    if not vertical:
        return None

    # gate: must have industry overlap (direct or adjacent) AND state overlap
    direct = account["industry"] in industries
    adjacent = bool(industries & ADJACENT_INDUSTRIES.get(account["industry"], set()))
    if not (direct or adjacent):
        return None
    if bill["state"] not in account["state_footprint"]:
        return None

    weights = vertical["weights"]
    industry_match = 1.0 if direct else 0.4
    urgency_norm = (cls.get("urgency", 1) or 1) / 5.0
    state_overlap = 1.0  # gated above
    engagement = ENGAGEMENT_SCORES.get(account["engagement_status"], 0.4)

    breakdown = {
        "industry_match": industry_match * weights["industry_match"],
        "urgency": urgency_norm * weights["urgency"],
        "state_footprint_overlap": state_overlap * weights["state_footprint_overlap"],
        "engagement": engagement * weights["engagement"],
    }
    total = round(sum(breakdown.values()), 4)
    return Match(bill=bill, account=account, score=total, breakdown=breakdown)


def match_and_score(bills: list[dict[str, Any]], accounts: list[dict[str, Any]], cfg: dict[str, Any]) -> list[Match]:
    matches = []
    for b in bills:
        if not b.get("classification"):
            continue
        for a in accounts:
            m = score_pair(b, a, cfg)
            if m is None:
                continue
            vertical = cfg["verticals"][a["vertical_config"]]
            urgency = (b["classification"].get("urgency") or 0)
            if m.score >= 0.6 and urgency >= vertical["urgency_floor"]:
                matches.append(m)
    return matches


# ---------- step 4: draft & route ----------

DRAFTER_SYSTEM = (
    "You are drafting a sales briefing for a state policy intelligence platform's GTM team. "
    "Tone: confident, factual, no hype, no exclamation. "
    "Output the briefing only — no preamble, no signature."
)

DRAFTER_USER_TMPL = """Account: {account_name} ({industry})
Account state footprint: {footprint}
Bill: {identifier} — {title} ({state})
Topic: {topic}
Urgency: {urgency}/5
Latest action: {latest_action} on {latest_action_date}

Write a 3-part briefing for the AE:
1. Why now — one sentence on the trigger.
2. Why this account — one sentence on the specific exposure.
3. Suggested open — one sentence the AE could lead with.

Total length under 80 words."""


def draft_briefing(client: Anthropic, m: Match, model: str) -> tuple[str, dict[str, int]]:
    cls = m.bill["classification"]
    msg = client.messages.create(
        model=model,
        max_tokens=300,
        system=DRAFTER_SYSTEM,
        messages=[{"role": "user", "content": DRAFTER_USER_TMPL.format(
            account_name=m.account["name"], industry=m.account["industry"],
            footprint=", ".join(m.account["state_footprint"][:8]),
            identifier=m.bill["identifier"], title=m.bill["title"], state=m.bill["state"].upper(),
            topic=cls.get("topic_summary", ""), urgency=cls.get("urgency", 0),
            latest_action=m.bill["latest_action"], latest_action_date=m.bill["latest_action_date"]
        )}],
    )
    return msg.content[0].text.strip(), {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}


CAP_HUBSPOT_PER_AE = 3
CAP_SEQUENCE_PER_AE = 5
CAP_SLACK_PER_AE = 3


def route_matches(client: Anthropic | None, matches: list[Match]) -> dict[str, list[dict[str, Any]]]:
    """Route matches to action queues with per-AE daily caps.

    Caps prevent the firehose problem: 92 active bills against 60 accounts can
    produce 300+ matches in a day, which would overwhelm 5 AEs. Per-AE caps
    keep the daily action volume realistic. Highest-scoring matches win.
    """
    from collections import defaultdict

    hubspot, sequences, slack = [], [], []
    drafter_usage = {"opus_input": 0, "opus_output": 0, "sonnet_input": 0, "sonnet_output": 0}
    ae_hubspot_count: dict[str, int] = defaultdict(int)
    ae_sequence_count: dict[str, int] = defaultdict(int)
    ae_slack_count: dict[str, int] = defaultdict(int)

    seen = set()
    matches_sorted = sorted(matches, key=lambda x: -x.score)

    for m in matches_sorted:
        key = (m.bill["id"], m.account["id"])
        if key in seen:
            continue
        seen.add(key)

        urgency = m.bill["classification"].get("urgency", 0)
        is_top_tier = m.score >= 0.8 and m.account["tier"] <= 2
        ae = m.account["owner_ae"]

        # urgency=5 -> Slack (capped per AE)
        if urgency == 5 and ae_slack_count[ae] < CAP_SLACK_PER_AE:
            ae_slack_count[ae] += 1
            slack.append({
                "timestamp": _now(),
                "channel": "#gtm-policy-alerts",
                "account_id": m.account["id"],
                "account_name": m.account["name"],
                "owner_ae": m.account["owner_ae"],
                "bill_identifier": m.bill["identifier"],
                "bill_title": m.bill["title"],
                "bill_state": m.bill["state"].upper(),
                "bill_url": m.bill["url"],
                "score": m.score,
                "message": f":rotating_light: URGENT — {m.account['name']} exposed: {m.bill['identifier']} ({m.bill['state'].upper()}) at urgency 5. {m.bill['classification'].get('topic_summary','')}",
            })
            continue

        if is_top_tier and ae_hubspot_count[ae] < CAP_HUBSPOT_PER_AE:
            ae_hubspot_count[ae] += 1
            briefing, usage = draft_briefing(client, m, "claude-opus-4-7") if client else ("[live mode required]", {"input_tokens": 0, "output_tokens": 0})
            drafter_usage["opus_input"] += usage["input_tokens"]
            drafter_usage["opus_output"] += usage["output_tokens"]
            hubspot.append(_build_task(m, briefing, model="claude-opus-4-7"))
        elif ae_sequence_count[ae] < CAP_SEQUENCE_PER_AE:
            ae_sequence_count[ae] += 1
            briefing, usage = draft_briefing(client, m, "claude-sonnet-4-6") if client else ("[live mode required]", {"input_tokens": 0, "output_tokens": 0})
            drafter_usage["sonnet_input"] += usage["input_tokens"]
            drafter_usage["sonnet_output"] += usage["output_tokens"]
            sequences.append(_build_sequence_step(m, briefing, model="claude-sonnet-4-6"))

    return {
        "hubspot_tasks": hubspot,
        "sequences": sequences,
        "slack_alerts": slack,
        "drafter_usage": drafter_usage,
    }


def _build_task(m: Match, briefing: str, model: str) -> dict[str, Any]:
    return {
        "task_id": f"task_{m.bill['identifier'].replace(' ','')}_{m.account['id']}",
        "owner_ae": m.account["owner_ae"],
        "account_id": m.account["id"],
        "account_name": m.account["name"],
        "subject": f"[Policy Signal] {m.bill['identifier']} ({m.bill['state'].upper()}) — {m.account['name']}",
        "body": briefing,
        "due_in_days": 2,
        "score": m.score,
        "score_breakdown": m.breakdown,
        "bill": {
            "id": m.bill["id"], "identifier": m.bill["identifier"],
            "state": m.bill["state"].upper(), "title": m.bill["title"],
            "url": m.bill["url"], "urgency": m.bill["classification"]["urgency"],
        },
        "drafted_by": model,
        "created_at": _now(),
    }


def _build_sequence_step(m: Match, briefing: str, model: str) -> dict[str, Any]:
    return {
        "sequence_id": f"seq_{m.account['vertical_config']}_weekly",
        "step": "policy_signal_touch",
        "account_id": m.account["id"],
        "account_name": m.account["name"],
        "owner_ae": m.account["owner_ae"],
        "subject_line": f"{m.bill['identifier']} just moved in {m.bill['state'].upper()} — relevant to {m.account['name']}?",
        "body": briefing,
        "score": m.score,
        "bill_identifier": m.bill["identifier"],
        "bill_url": m.bill["url"],
        "drafted_by": model,
        "queued_at": _now(),
    }


# ---------- step 5: log ----------

def log_outcomes(matches: list[Match], routed: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    entries = []
    seen = set()
    for m in matches:
        key = (m.bill["id"], m.account["id"])
        if key in seen:
            continue
        seen.add(key)
        urgency = m.bill["classification"].get("urgency", 0)
        action = "slack_alert" if urgency == 5 else ("hubspot_task" if (m.score >= 0.8 and m.account["tier"] <= 2) else "sequence_enroll")
        entries.append({
            "timestamp": _now(),
            "bill_id": m.bill["id"],
            "bill_identifier": m.bill["identifier"],
            "account_id": m.account["id"],
            "score": m.score,
            "action_taken": action,
            "outcome": None,
            "outcome_logged_at": None,
        })
    return entries


# ---------- helpers ----------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str))


# ---------- entry ----------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--states", default=",".join(DEFAULT_STATES))
    p.add_argument("--since", type=int, default=1, help="days back to fetch")
    args = p.parse_args()

    states = [s.strip().lower() for s in args.states.split(",") if s.strip()]
    accounts = load_accounts()
    cfg = load_scoring_config()

    if args.dry_run:
        sample_path = DATA / "sample_raw_bills.json"
        if not sample_path.exists():
            print(f"missing {sample_path}; cannot dry-run", file=sys.stderr)
            return 2
        bills = json.loads(sample_path.read_text())
        client = None
        errors = ErrorLog(ERROR_PATH)
        sample_classified = DATA / "sample_classified_bills.json"
        if sample_classified.exists():
            bills = json.loads(sample_classified.read_text())
        classifier_usage = {"input_tokens": 0, "output_tokens": 0}
        print(f"[dry-run] loaded {len(bills)} sample bills")
    else:
        os_key = os.environ.get("OPENSTATES_API_KEY")
        ak_key = os.environ.get("ANTHROPIC_API_KEY")
        if not os_key or not ak_key:
            print("set OPENSTATES_API_KEY and ANTHROPIC_API_KEY, or use --dry-run", file=sys.stderr)
            return 2
        client = Anthropic(api_key=ak_key)
        cache = ClassificationCache(CACHE_PATH)
        errors = ErrorLog(ERROR_PATH)
        print(f"[live] fetching bills updated in last {args.since}d across {len(states)} states")
        try:
            bills = fetch_openstates_bills(os_key, states, args.since)
        except Exception as e:
            errors.error("fetch", e, context={"states": states, "since_days": args.since})
            errors.flush()
            raise
        _write_json(OUTPUTS / "raw_bills.json", bills)
        print(f"[live] fetched {len(bills)} bills; classifying ({cache.stats()['entries']} cached entries available)")
        bills, classifier_usage, cache_stats = classify_bills(client, bills, cache=cache, errors=errors)
        cache.flush()
        print(f"[live] classifier cache: {cache_stats['hits']} hits, {cache_stats['misses']} misses")
        _write_json(OUTPUTS / "classified_bills.json", bills)

    matches = match_and_score(bills, accounts, cfg)
    _write_json(OUTPUTS / "matches.json", [
        {"bill_id": m.bill["id"], "bill_identifier": m.bill["identifier"], "bill_state": m.bill["state"],
         "account_id": m.account["id"], "account_name": m.account["name"], "score": m.score,
         "breakdown": m.breakdown} for m in matches
    ])
    print(f"[match] {len(matches)} bill x account pairs above threshold")

    routed = route_matches(client, matches)
    _write_json(OUTPUTS / "hubspot_tasks.json", routed["hubspot_tasks"])
    _write_json(OUTPUTS / "sequences.json", routed["sequences"])
    _write_json(OUTPUTS / "slack_alerts.json", routed["slack_alerts"])

    outcomes = log_outcomes(matches, routed)
    outcomes_path = DATA / "outcomes.json"
    existing = json.loads(outcomes_path.read_text()) if outcomes_path.exists() else []
    _write_json(outcomes_path, existing + outcomes)

    summary = {
        "run_at": _now(),
        "mode": "dry-run" if args.dry_run else "live",
        "states": states,
        "since_days": args.since,
        "bills_fetched": len(bills),
        "matches_above_threshold": len(matches),
        "hubspot_tasks": len(routed["hubspot_tasks"]),
        "sequences": len(routed["sequences"]),
        "slack_alerts": len(routed["slack_alerts"]),
        "claude_usage": {
            "classifier": classifier_usage,
            "drafter": routed["drafter_usage"],
        },
        "estimated_cost_usd": _estimate_cost(classifier_usage, routed["drafter_usage"]),
    }
    _write_json(OUTPUTS / "run_summary.json", summary)
    if 'errors' in locals():
        errors.flush()
    print(json.dumps(summary, indent=2))
    return 0


def _estimate_cost(classifier: dict[str, int], drafter: dict[str, int]) -> float:
    # Sonnet 4.6: $3/M in, $15/M out. Opus 4.7: $15/M in, $75/M out. (Approx, public list prices.)
    sonnet_in = (classifier["input_tokens"] + drafter["sonnet_input"]) / 1_000_000 * 3.0
    sonnet_out = (classifier["output_tokens"] + drafter["sonnet_output"]) / 1_000_000 * 15.0
    opus_in = drafter["opus_input"] / 1_000_000 * 15.0
    opus_out = drafter["opus_output"] / 1_000_000 * 75.0
    return round(sonnet_in + sonnet_out + opus_in + opus_out, 4)


if __name__ == "__main__":
    sys.exit(main())
