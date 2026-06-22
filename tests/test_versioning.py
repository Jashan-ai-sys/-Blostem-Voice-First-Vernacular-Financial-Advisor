"""
Version manager / dual-index tests — pure, offline.
Run:  python -m pytest tests/test_versioning.py   OR   python tests/test_versioning.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.versioning import (
    content_hash, vector_id, plan_versioned, active_chunk_ids, version_as_of,
)


def _chunk(cid, text):
    return {"chunk_id": cid, "text": text, "metadata": {"source": "s.md"}}


def test_vector_id_format():
    assert vector_id("fn_121__p000", 3) == "fn_121__p000__v3"


def test_first_run_creates_v1_active():
    plan, m = plan_versioned([_chunk("a", "x"), _chunk("b", "y")], {}, now="2026-01-01")
    assert len(plan["to_embed"]) == 2
    assert all(v == 1 for _, v in plan["to_embed"])
    assert active_chunk_ids(m) == ["a", "b"]
    assert m["a"][0]["is_active"] and m["a"][0]["valid_to"] is None


def test_unchanged_is_skipped():
    _, m = plan_versioned([_chunk("a", "x")], {}, now="2026-01-01")
    plan, m2 = plan_versioned([_chunk("a", "x")], m, now="2026-02-01")
    assert plan["skipped"] == ["a"] and plan["to_embed"] == []


def test_change_deactivates_old_adds_new_version():
    _, m = plan_versioned([_chunk("a", "x")], {}, now="2026-01-01")
    plan, m2 = plan_versioned([_chunk("a", "x-UPDATED")], m, now="2026-02-01")
    # new version embedded
    assert [(c["chunk_id"], v) for c, v in plan["to_embed"]] == [("a", 2)]
    # old version retired (deactivated, not deleted)
    assert plan["deactivate"] == ["a__v1"]
    versions = m2["a"]
    assert len(versions) == 2  # history preserved
    assert versions[0]["is_active"] is False and versions[0]["valid_to"] == "2026-02-01"
    assert versions[1]["is_active"] is True and versions[1]["version"] == 2


def test_removed_chunk_retired_not_deleted():
    _, m = plan_versioned([_chunk("a", "x"), _chunk("b", "y")], {}, now="2026-01-01")
    plan, m2 = plan_versioned([_chunk("a", "x")], m, now="2026-03-01")  # b removed
    assert plan["removed"] == ["b"]
    assert plan["deactivate"] == ["b__v1"]
    assert "b" in m2  # still present in history
    assert active_chunk_ids(m2) == ["a"]  # b no longer active


def test_version_as_of_historical_lookup():
    _, m = plan_versioned([_chunk("a", "v1text")], {}, now="2026-01-01")
    _, m = plan_versioned([_chunk("a", "v2text")], m, now="2026-06-01")
    assert version_as_of(m, "a", "2026-03-15") == 1   # mid-Jan..Jun → v1
    assert version_as_of(m, "a", "2026-07-01") == 2   # after Jun → v2
    assert version_as_of(m, "a", "2025-12-01") is None  # before it existed


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} versioning tests passed")


if __name__ == "__main__":
    _run()
