"""Tests for the classification cache: hit/miss + invalidation behavior."""
import json
from pathlib import Path

import pytest

from _lib.cache import ClassificationCache


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "cache.json"


def test_empty_cache_returns_none(cache_path):
    c = ClassificationCache(cache_path)
    assert c.get("ocd-bill/x", "2026-05-01") is None


def test_put_then_get(cache_path):
    c = ClassificationCache(cache_path)
    cls = {"industries": ["insurance"], "urgency": 4}
    c.put("ocd-bill/x", "2026-05-01", cls)
    assert c.get("ocd-bill/x", "2026-05-01") == cls


def test_invalidation_on_action_date_change(cache_path):
    """A bill that has moved (new latest_action_date) must miss the cache."""
    c = ClassificationCache(cache_path)
    c.put("ocd-bill/x", "2026-05-01", {"industries": ["insurance"], "urgency": 3})
    # bill's latest_action_date changed -> cache entry is stale
    assert c.get("ocd-bill/x", "2026-05-10") is None


def test_flush_persists(cache_path):
    c = ClassificationCache(cache_path)
    c.put("ocd-bill/y", "2026-05-01", {"industries": ["energy"], "urgency": 2})
    c.flush()
    # new instance reads from disk
    c2 = ClassificationCache(cache_path)
    assert c2.get("ocd-bill/y", "2026-05-01") == {"industries": ["energy"], "urgency": 2}


def test_corrupt_file_recovers(cache_path):
    cache_path.write_text("{not valid json}")
    c = ClassificationCache(cache_path)  # should not raise
    assert c.get("anything", "anydate") is None
