"""
Classification cache.

Keyed by bill_id, invalidated when the bill's latest_action_date changes.
Backed by a single JSON file at data/classification_cache.json. In production
this would be Redis, KV, or a Postgres table; the interface stays the same.

Design:
  - Reads are O(1) via dict lookup.
  - Writes are batched at session end via flush(); avoids per-bill disk IO.
  - Invalidation is automatic on latest_action_date change (the only field
    that meaningfully shifts a bill's classification).

Cost impact:
  At 92 bills/day with ~30 of those changed since yesterday, the cache cuts
  Sonnet classifier calls from 92 to ~30 — roughly 70% steady-state savings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ClassificationCache:
    def __init__(self, path: Path):
        self.path = path
        self._cache: dict[str, dict[str, Any]] = {}
        self._dirty = False
        if path.exists():
            try:
                self._cache = json.loads(path.read_text())
            except json.JSONDecodeError:
                self._cache = {}

    def get(self, bill_id: str, latest_action_date: str | None) -> dict | None:
        """Returns classification dict if cached and still valid, else None."""
        entry = self._cache.get(bill_id)
        if not entry:
            return None
        if entry.get("latest_action_date") != latest_action_date:
            return None  # stale; bill has moved
        return entry.get("classification")

    def put(self, bill_id: str, latest_action_date: str | None, classification: dict) -> None:
        self._cache[bill_id] = {
            "latest_action_date": latest_action_date,
            "classification": classification,
        }
        self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._cache, indent=2))
        self._dirty = False

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._cache)}
