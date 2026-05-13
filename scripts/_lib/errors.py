"""
Structured error logging.

Every pipeline-level failure (HTTP error, classifier parse error, drafter
timeout) appends a row to data/errors.json. RevOps gets a single file to
grep when something looks off, and the row includes enough context to
reproduce.

Schema:
  {
    "timestamp": ISO8601 UTC,
    "stage": "fetch" | "classify" | "draft" | "route" | "log",
    "level": "warn" | "error",
    "context": {bill_id?, account_id?, state?, ...},
    "exception_type": "<ClassName>",
    "message": "<str>"
  }
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ErrorLog:
    def __init__(self, path: Path):
        self.path = path
        self._buf: list[dict[str, Any]] = []

    def warn(self, stage: str, message: str, context: dict | None = None) -> None:
        self._record(stage, "warn", message, context, exc=None)

    def error(self, stage: str, exc: Exception, context: dict | None = None) -> None:
        self._record(stage, "error", str(exc), context, exc=exc)

    def _record(self, stage: str, level: str, message: str, context: dict | None, exc: Exception | None) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stage": stage,
            "level": level,
            "context": context or {},
            "exception_type": type(exc).__name__ if exc else None,
            "message": message,
        }
        if exc is not None:
            row["traceback"] = traceback.format_exception(type(exc), exc, exc.__traceback__)[-3:]
        self._buf.append(row)

    def flush(self) -> None:
        if not self._buf:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if self.path.exists():
            try:
                existing = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                existing = []
        self.path.write_text(json.dumps(existing + self._buf, indent=2))
        self._buf = []

    def count(self) -> int:
        return len(self._buf)
