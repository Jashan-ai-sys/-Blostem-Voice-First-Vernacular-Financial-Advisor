"""
Wave-3 ingestion tests — change detection is pure, so fully offline.
Run:  python -m pytest tests/test_ingestion.py   OR   python tests/test_ingestion.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion import content_hash, plan_ingest, load_chunks


def _chunk(cid, text, source="s.md"):
    return {"chunk_id": cid, "text": text, "metadata": {"source": source}}


def test_hash_is_deterministic_and_sensitive():
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("hello!")


def test_plan_first_run_embeds_everything():
    chunks = [_chunk("a", "x"), _chunk("b", "y")]
    plan = plan_ingest(chunks, manifest={})
    assert len(plan["to_embed"]) == 2
    assert plan["skipped"] == [] and plan["to_delete"] == []


def test_plan_skips_unchanged():
    chunks = [_chunk("a", "x"), _chunk("b", "y")]
    manifest = {"a": {"hash": content_hash("x")}, "b": {"hash": content_hash("y")}}
    plan = plan_ingest(chunks, manifest)
    assert plan["to_embed"] == [] and set(plan["skipped"]) == {"a", "b"}


def test_plan_re_embeds_changed_only():
    chunks = [_chunk("a", "x-NEW"), _chunk("b", "y")]
    manifest = {"a": {"hash": content_hash("x")}, "b": {"hash": content_hash("y")}}
    plan = plan_ingest(chunks, manifest)
    assert [c["chunk_id"] for c in plan["to_embed"]] == ["a"]
    assert plan["skipped"] == ["b"]


def test_plan_deletes_removed_chunks():
    chunks = [_chunk("a", "x")]
    manifest = {"a": {"hash": content_hash("x")}, "gone": {"hash": "deadbeef"}}
    plan = plan_ingest(chunks, manifest)
    assert plan["to_delete"] == ["gone"]


def test_real_corpus_has_unique_ids():
    chunks = load_chunks()
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "chunk_ids must be unique (no cross-file collisions)"
    assert len(ids) > 500


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} ingestion tests passed")


if __name__ == "__main__":
    _run()
