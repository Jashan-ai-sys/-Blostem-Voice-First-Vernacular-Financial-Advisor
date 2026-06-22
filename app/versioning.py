"""
Version Manager + Dual Index (Phase 4 & 7)
==========================================
Each chunk keeps a VERSION HISTORY. The latest version is "active"; older ones
are "deactivated" — never deleted. This gives two logical indexes over one
physical Pinecone index:

  - ACTIVE index    → current knowledge (retrieval queries this by default)
  - HISTORICAL index → every version ever (for "what did the policy say in Jan?")

Realized via metadata on one index: each chunk version is a vector
`{chunk_id}__v{n}` with metadata {chunk_id, version, is_active, valid_from,
valid_to}. Active retrieval filters is_active=True; historical retrieval filters
by valid_from/valid_to. Deactivation is a metadata UPDATE, not a delete — history
is preserved (Phase 4 "never delete, only deactivate").

This module is the pure version manager (the file-based manifest is the
document_versions table; Postgres is the production target). The Pinecone wiring
lives in app/ingestion.run_ingest behind settings.VERSIONED_INDEX.
"""

from __future__ import annotations

import copy
import hashlib


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def vector_id(chunk_id: str, version: int) -> str:
    return f"{chunk_id}__v{version}"


def _versions(manifest: dict, chunk_id: str) -> list:
    v = manifest.get(chunk_id)
    if not isinstance(v, list):  # tolerate empty / legacy-flat entries
        v = []
        manifest[chunk_id] = v
    return v


def _active(versions: list) -> dict | None:
    for v in reversed(versions):
        if v.get("is_active"):
            return v
    return None


def plan_versioned(chunks: list[dict], manifest: dict, now: str) -> tuple[dict, dict]:
    """Diff the corpus against the versioned manifest. Pure (returns a new manifest).

    Returns (plan, manifest) where plan = {
        to_embed:  [(chunk, version)]   new/changed chunks needing embedding
        deactivate:[vector_id]          prior versions to flip is_active=False
        skipped:   [chunk_id]           unchanged
        removed:   [chunk_id]           gone from corpus → active version retired
    }
    """
    manifest = copy.deepcopy(manifest)
    to_embed, skipped, deactivate, removed = [], [], [], []
    current: set[str] = set()

    for chunk in chunks:
        cid = chunk.get("chunk_id")
        if not cid:
            continue
        current.add(cid)
        h = content_hash(chunk.get("text", ""))
        versions = _versions(manifest, cid)
        active = _active(versions)

        if active and active["hash"] == h:
            skipped.append(cid)
            continue

        new_version = (active["version"] + 1) if active else 1
        if active:  # retire the old version (keep it, just deactivate)
            active["is_active"] = False
            active["valid_to"] = now
            deactivate.append(vector_id(cid, active["version"]))
        versions.append({
            "version": new_version, "hash": h,
            "valid_from": now, "valid_to": None, "is_active": True,
        })
        to_embed.append((chunk, new_version))

    # Chunks removed from the corpus: retire their active version (never delete).
    for cid, versions in manifest.items():
        if cid in current:
            continue
        active = _active(versions)
        if active:
            active["is_active"] = False
            active["valid_to"] = now
            deactivate.append(vector_id(cid, active["version"]))
            removed.append(cid)

    return {"to_embed": to_embed, "deactivate": deactivate,
            "skipped": skipped, "removed": removed}, manifest


def active_chunk_ids(manifest: dict) -> list[str]:
    """The active index: chunk_ids whose latest version is active."""
    return [cid for cid, versions in manifest.items()
            if isinstance(versions, list) and _active(versions)]


def version_as_of(manifest: dict, chunk_id: str, ts: str) -> int | None:
    """Historical lookup: which version was active at timestamp `ts`."""
    for v in manifest.get(chunk_id, []):
        vf, vt = v["valid_from"], v["valid_to"]
        if vf <= ts and (vt is None or ts < vt):
            return v["version"]
    return None
