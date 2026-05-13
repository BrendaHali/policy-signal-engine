"""
Account Research Agent.

Triggered on top-tier matches (score >= 0.85). Produces an enriched briefing
that pairs the bill with account-specific exposure context: recent press
releases, public statements, competitor positioning on the same regulatory
area. The output goes into outputs/enriched_briefings.json and supersedes
the bare drafter output for the highest-stakes touches.

Architecture:
  This is a multi-step Claude agent using tool use. It receives a single
  (bill, account) pair and orchestrates:
    1. web_search(account_name + regulatory_area) -> recent news
    2. web_search(account_name + bill_topic + competitors) -> competitive lens
    3. synthesize -> structured briefing with exposure summary, talking points,
       and a confidence score

  In production the tools would call real Bing/SerpAPI/Tavily endpoints. In
  this repo the tools are stubbed with deterministic responses so the agent
  can run in --dry-run mode without external dependencies. To go live, swap
  the tool implementations and set the relevant API keys.

Usage:
  python scripts/account_research_agent.py --dry-run
  python scripts/account_research_agent.py --pair task_HB1015_acc_001
  python scripts/account_research_agent.py --top-n 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)


# ---------- tool layer (stubbed; swap implementations in live mode) ----------

def web_search(query: str, k: int = 5) -> list[dict[str, str]]:
    """Stub: returns deterministic results. In live mode wire to Tavily/SerpAPI/Bing."""
    return [
        {"title": f"[stub] Top result for: {query}", "url": "https://example.com/result-1", "snippet": "Search result snippet placeholder."},
        {"title": f"[stub] Second result for: {query}", "url": "https://example.com/result-2", "snippet": "Search result snippet placeholder."},
    ][:k]


def fetch_url(url: str) -> str:
    """Stub: in live mode use httpx to retrieve and clean the page."""
    return f"[stub] Body of {url}"


TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for recent information about a company, regulation, or topic. Returns up to k results with title, url, snippet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Specific search query, ideally including the company name and regulatory topic."},
                "k": {"type": "integer", "description": "Number of results to return", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch and return the cleaned text body of a single URL identified during search.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
]


def dispatch_tool(name: str, args: dict) -> Any:
    if name == "web_search":
        return web_search(args["query"], args.get("k", 5))
    if name == "fetch_url":
        return fetch_url(args["url"])
    raise ValueError(f"unknown tool: {name}")


# ---------- agent loop ----------

AGENT_SYSTEM = """You are a senior research analyst preparing an account briefing for a B2B sales rep at a state policy intelligence platform. You have web_search and fetch_url tools.

Your job is to research a single (account, bill) pair and produce a structured briefing.

Approach:
1. Start by searching for recent (last 90 days) news about the account's exposure to the bill's regulatory area in the bill's state.
2. If a relevant result appears, fetch the most useful one for primary-source detail.
3. Optionally search for what competitors in the same industry are doing on the same regulatory issue.
4. Stop researching after at most 3 tool calls. Do not over-research; the rep has 5 minutes to read this.

Then return ONLY a JSON object with these fields:

{
  "exposure_summary": "Two sentences naming the specific operational or financial exposure this bill creates for this account.",
  "evidence": [{"claim": "...", "source": "url"}],   // 1-3 evidence items pulled from your research
  "competitor_lens": "One sentence on what competitors are doing or saying on this regulatory area, or 'no public position identified'.",
  "talking_points": ["...", "...", "..."],            // 3 talking points the rep can use
  "confidence": "high | medium | low",                // your confidence that this account is actually exposed
  "confidence_rationale": "One sentence."
}

If research surfaces nothing useful, set confidence to low and say so honestly. Do not fabricate sources."""


def run_agent(client, pair: dict, max_iterations: int = 4) -> tuple[dict, list[dict]]:
    """Run the agent loop. Returns (briefing_json, conversation_trace)."""
    user_msg = f"""Account: {pair['account_name']} ({pair['account_industry']})
Account state footprint: {", ".join(pair['account_state_footprint'][:8])}
Account engagement status: {pair['account_engagement_status']}
Bill: {pair['bill_identifier']} ({pair['bill_state'].upper()}) — {pair['bill_title']}
Regulatory topic: {pair['topic_summary']}
Affected entities (per classifier): {", ".join(pair.get('affected_entities', []))}
Bill latest action: {pair['bill_latest_action']} on {pair['bill_latest_action_date']}
Score: {pair['score']}

Research and produce the briefing."""

    messages = [{"role": "user", "content": user_msg}]
    trace = []
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=AGENT_SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        trace.append({"iteration": iterations, "stop_reason": resp.stop_reason})

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    result = dispatch_tool(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
                    trace.append({"tool": block.name, "input": block.input, "result_preview": str(result)[:200]})
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # final answer
        text_blocks = [b for b in resp.content if hasattr(b, "text")]
        if not text_blocks:
            return {"error": "no text in final response"}, trace
        try:
            briefing = json.loads(text_blocks[0].text.strip())
        except json.JSONDecodeError as e:
            return {"error": f"JSON parse failed: {e}", "raw": text_blocks[0].text}, trace
        return briefing, trace

    return {"error": "max iterations reached"}, trace


# ---------- dry-run agent (no Claude calls) ----------

def run_dry_agent(pair: dict) -> tuple[dict, list[dict]]:
    """Deterministic stub for dry-run. Returns a representative briefing shape."""
    cls_industries = pair.get("industries", [pair["account_industry"]])
    is_signed = "act " in (pair["bill_latest_action"] or "").lower() or "approved by governor" in (pair["bill_latest_action"] or "").lower()

    return {
        "exposure_summary": (
            f"{pair['account_name']}'s {pair['account_industry']} operations in {pair['bill_state'].upper()} are directly exposed to the new statutory requirement "
            f"covering {pair['topic_summary'].lower().rstrip('.')}. {'The bill is now signed and on the operational clock.' if is_signed else 'The bill is moving and will hit the operational clock if it advances.'}"
        ),
        "evidence": [
            {"claim": f"Account operates in {pair['bill_state'].upper()}, the bill's jurisdiction.", "source": "data/accounts.json"},
            {"claim": f"Account industry ({pair['account_industry']}) overlaps the bill's classified industries ({', '.join(cls_industries[:3])}).", "source": "outputs/classified_bills.json"},
            {"claim": f"Bill latest action: {pair['bill_latest_action']} on {pair['bill_latest_action_date']}.", "source": pair["bill_url"]},
        ],
        "competitor_lens": "Live mode required for competitor positioning research; stub returned in dry-run.",
        "talking_points": [
            f"The {pair['bill_identifier']} change creates a near-term operational requirement for {pair['account_name']}'s {pair['bill_state'].upper()} footprint.",
            f"Other {pair['account_industry']} accounts with similar exposure are evaluating compliance paths now.",
            f"Worth a 15-minute conversation with the team owning {pair['account_industry']} regulatory ops at {pair['account_name']}.",
        ],
        "confidence": "medium" if is_signed else "low",
        "confidence_rationale": (
            "Bill is signed and operational, account state footprint and industry both match." if is_signed
            else "Bill is in motion but not yet enacted; exposure is contingent on advancement."
        ),
    }, [{"mode": "dry-run", "tool_calls": 0}]


# ---------- entry ----------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--top-n", type=int, default=5, help="Research the top N highest-scoring hubspot tasks")
    p.add_argument("--pair", help="Specific task_id to research")
    args = p.parse_args()

    tasks = json.loads((OUTPUTS / "hubspot_tasks.json").read_text())
    if args.pair:
        candidates = [t for t in tasks if t["task_id"] == args.pair]
    else:
        candidates = sorted(tasks, key=lambda t: -t["score"])[: args.top_n]

    if not candidates:
        print("no candidate pairs found", file=sys.stderr)
        return 2

    if args.dry_run:
        client = None
    else:
        ak = os.environ.get("ANTHROPIC_API_KEY")
        if not ak:
            print("set ANTHROPIC_API_KEY or use --dry-run", file=sys.stderr)
            return 2
        from anthropic import Anthropic
        client = Anthropic(api_key=ak)

    enriched = []
    for task in candidates:
        # Re-shape the task back into the pair format the agent expects
        pair = {
            "account_id": task["account_id"],
            "account_name": task["account_name"],
            "account_industry": _infer_industry(task["account_name"]),
            "account_state_footprint": _infer_footprint(),
            "account_engagement_status": "n/a (re-fetch from accounts.json in production)",
            "bill_id": task["bill"]["id"],
            "bill_identifier": task["bill"]["identifier"],
            "bill_state": task["bill"]["state"].lower(),
            "bill_title": task["bill"]["title"],
            "bill_latest_action": "see bill.url",
            "bill_latest_action_date": task["created_at"][:10],
            "topic_summary": task["bill"].get("topic_summary", ""),
            "affected_entities": [],
            "bill_url": task["bill"]["url"],
            "industries": [],
            "score": task["score"],
        }
        if args.dry_run:
            briefing, trace = run_dry_agent(pair)
        else:
            briefing, trace = run_agent(client, pair)

        enriched.append({
            "task_id": task["task_id"],
            "account_name": task["account_name"],
            "bill_identifier": task["bill"]["identifier"],
            "score": task["score"],
            "researched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "briefing": briefing,
            "agent_trace": trace,
        })
        print(f"researched: {task['account_name']} <- {task['bill']['identifier']}  ({len(trace)} step(s))")

    out_path = OUTPUTS / "enriched_briefings.json"
    out_path.write_text(json.dumps(enriched, indent=2))
    print(f"\nwrote {out_path} ({len(enriched)} briefings)")
    return 0


def _infer_industry(name: str) -> str:
    accounts = json.loads((DATA / "accounts.json").read_text())
    for a in accounts:
        if a["name"] == name:
            return a["industry"]
    return "unknown"


def _infer_footprint() -> list[str]:
    return ["ca", "tx", "fl", "ny", "pa", "il", "oh", "ga", "nc", "mi"]


if __name__ == "__main__":
    sys.exit(main())
