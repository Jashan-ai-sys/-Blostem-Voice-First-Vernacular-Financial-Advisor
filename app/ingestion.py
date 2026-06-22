"""
Ingestion Service — knowledge lifecycle (Wave 3)
================================================
Re-runnable, idempotent ingestion that replaces the old one-shot upsert script.

    chunks.jsonl ─→ content-hash change detection ─→ embed ONLY new/changed
                 ─→ idempotent Pinecone upsert ─→ delete stale ─→ version manifest

Change detection (Phase 5): each chunk's text is SHA-256 hashed and compared to
the manifest from the last run. Unchanged chunks are skipped — no re-embedding,
which is where the embedding-cost savings come from. Chunks that disappeared
from the corpus are deleted from the index so it never drifts from source.

The manifest (data/chunks/ingest_manifest.json) is the lightweight version
record. Full active/historical dual-index is the next sub-step; this establishes
the hash + version foundation it builds on.

`plan_ingest` is pure and unit-tested; `run_ingest` does the I/O (needs API keys).
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from app.config import settings

_OPEN_TS = 9_999_999_999  # "still active" sentinel for valid_to (year ~2286)
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CHUNKS_PATH = os.path.join(_DATA_DIR, "chunks", "retrieval_chunks.jsonl")
MANIFEST_PATH = os.path.join(_DATA_DIR, "chunks", "ingest_manifest.json")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hype_types() -> set[str]:
    """Chunk types that get HyPE questions (non-child by default — children are
    sub-parts of parents, so HyPE on parents covers them without extra LLM calls)."""
    return {t.strip() for t in settings.HYPE_CHUNK_TYPES.split(",") if t.strip()}


def load_chunks(path: str = CHUNKS_PATH) -> list[dict]:
    chunks = []
    if not os.path.exists(path):
        return chunks
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


OKF_DIR = os.path.join(_DATA_DIR, "okf")


def load_okf_chunks(root: str = OKF_DIR) -> list[dict]:
    """OKF bundle (screens/concepts/errors as markdown) → retrieval chunks.
    Returns [] if no bundle exists yet."""
    if not os.path.isdir(root):
        return []
    from app import okf
    return okf.okf_to_chunks(root)


def load_index_corpus() -> list[dict]:
    """The corpus used to BUILD the index (dense + BM25): the document corpus from
    retrieval_chunks.jsonl MINUS the legacy `screen_graph` chunks (now superseded),
    PLUS the OKF bundle — the source of truth for screen/concept/error knowledge.
    Keeps load_chunks() pure for the add/remove write-path."""
    base = [c for c in load_chunks()
            if c.get("metadata", {}).get("doc_type") != "screen_graph"]
    return base + load_okf_chunks()


def load_manifest(path: str = MANIFEST_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest: dict, path: str = MANIFEST_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def plan_ingest(chunks: list[dict], manifest: dict) -> dict:
    """Diff the corpus against the last-ingested manifest. Pure function.

    Returns {"to_embed": [chunk...], "skipped": [id...], "to_delete": [id...]}.
    A chunk is embedded if it's new or its text hash changed; skipped if its hash
    matches; deleted if it's in the manifest but no longer in the corpus.
    """
    to_embed, skipped = [], []
    current_ids = set()
    for chunk in chunks:
        cid = chunk.get("chunk_id")
        if not cid:
            continue
        current_ids.add(cid)
        prev = manifest.get(cid)
        if prev and prev.get("hash") == content_hash(chunk.get("text", "")):
            skipped.append(cid)
        else:
            to_embed.append(chunk)
    to_delete = [cid for cid in manifest if cid not in current_ids]
    return {"to_embed": to_embed, "skipped": skipped, "to_delete": to_delete}


def _source_prefix(chunk_id: str) -> str:
    return chunk_id.split("__", 1)[0]


def add_document_chunks(new_chunks: list[dict], path: str = CHUNKS_PATH) -> int:
    """Add a document's chunks to the corpus, replacing any prior chunks from the
    same source (so re-uploading an updated PDF refreshes cleanly). Returns count."""
    prefixes = {_source_prefix(c["chunk_id"]) for c in new_chunks if c.get("chunk_id")}
    kept = [c for c in load_chunks(path) if _source_prefix(c.get("chunk_id", "")) not in prefixes]
    kept.extend(new_chunks)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for chunk in kept:
            f.write(json.dumps(chunk) + "\n")
    return len(new_chunks)


def ingest_pdf_file(pdf_path: str, source_name: str | None = None, embed: bool = True) -> dict:
    """Self-serve ingestion: clean+chunk a PDF, add it to the corpus, refresh BM25
    (so chat/voice can answer immediately), and embed+upsert to Pinecone if keys
    are set. This is the engine behind POST /ingest/upload."""
    from app.chunking import chunk_pdf
    from app.retrieval import reload_bm25_index

    source = source_name or os.path.basename(pdf_path)
    chunks = chunk_pdf(pdf_path, source=source)
    added = add_document_chunks(chunks)
    reload_bm25_index()  # immediately searchable via BM25 (works even with no keys)

    summary = {"source": source, "chunks_added": added, "bm25_ready": True, "indexed": False}
    _embed_ready = settings.PINECONE_API_KEY and (
        settings.EMBEDDING_BACKEND == "local" or settings.GOOGLE_API_KEY
    )
    if embed and _embed_ready:
        result = run_ingest()  # change-detection embeds only the new/changed chunks
        summary["indexed"] = True
        summary["embedded"] = result.get("embedded", 0)
    return summary


def _flatten_metadata(chunk: dict) -> dict:
    """Pinecone metadata: text + chunk_id + flattened source metadata."""
    cid = chunk["chunk_id"]
    flat = {"text": chunk.get("text", ""), "chunk_id": cid}
    for k, v in chunk.get("metadata", {}).items():
        if v is None:
            continue  # Pinecone rejects null metadata values (e.g. app_step=null)
        flat[k] = ", ".join(str(x) for x in v) if isinstance(v, list) else v
    return flat


def _embed(text: str) -> list[float]:
    return _embed_many([text])[0]


def _embed_many(texts: list[str]) -> list[list[float]]:
    """Embed document texts. Local backend batches in-process (fast, no quota);
    Gemini backend falls back to per-text API calls."""
    if settings.EMBEDDING_BACKEND == "local":
        from app.embedder import embed_texts
        return embed_texts(texts, is_query=False)

    import google.generativeai as genai
    out = []
    for text in texts:
        result = genai.embed_content(
            model=settings.EMBEDDING_MODEL,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=settings.EMBEDDING_DIM,
        )
        out.append(result["embedding"])
    return out


def _open_index():
    """Open Pinecone (creating the index if missing) and configure the embedding
    backend. Local backend needs no GOOGLE_API_KEY; Gemini backend does."""
    if not settings.PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY must be set to run ingestion.")
    from pinecone import Pinecone, ServerlessSpec

    if settings.EMBEDDING_BACKEND == "gemini":
        if not settings.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY must be set for the gemini embedding backend.")
        import google.generativeai as genai
        genai.configure(api_key=settings.GOOGLE_API_KEY)

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    name = settings.PINECONE_INDEX_NAME
    if name not in pc.list_indexes().names():
        print(f"[ingest] creating index '{name}' (dim={settings.EMBEDDING_DIM}, cosine)...")
        pc.create_index(name=name, dimension=settings.EMBEDDING_DIM, metric="cosine",
                        spec=ServerlessSpec(cloud="aws", region="us-east-1"))
        while not pc.describe_index(name).status["ready"]:
            time.sleep(1)
    return pc.Index(name)


def run_ingest(dry_run: bool = False, batch_size: int = 50, version: str | None = None,
               reset: bool = False) -> dict:
    """Execute the ingestion plan. dry_run reports the plan without embedding or
    touching Pinecone. Honors settings.VERSIONED_INDEX for the dual active/historical
    index (Phase 7).

    reset=True: wipe ALL existing vectors and re-embed the whole corpus from an empty
    manifest. Required when switching embedding models (e.g. Gemini → local e5): the
    text is unchanged so change-detection would skip everything, yet the old vectors
    live in a different vector space and must be replaced wholesale."""
    chunks = load_chunks()
    manifest = {} if reset else load_manifest()

    if settings.VERSIONED_INDEX:
        return _run_ingest_versioned(chunks, manifest, dry_run, batch_size, version)

    plan = plan_ingest(chunks, manifest)
    summary = {"total_chunks": len(chunks), "versioned": False, "reset": reset,
               "backend": settings.EMBEDDING_BACKEND, "hype": settings.HYPE_ENABLED,
               "to_embed": len(plan["to_embed"]), "skipped": len(plan["skipped"]),
               "to_delete": len(plan["to_delete"])}
    print(f"[ingest] plan: {summary}")
    if dry_run:
        summary["dry_run"] = True
        return summary

    index = _open_index()
    if reset:
        print("[ingest] reset=True: deleting ALL existing vectors before re-embed...")
        try:
            index.delete(delete_all=True)
        except Exception as e:
            print(f"[ingest] delete_all failed (continuing, upsert overwrites by id): {e}")

    to_embed = plan["to_embed"]
    texts = [c.get("text", "") for c in to_embed]
    embeddings = _embed_many(texts) if texts else []  # batched in-process for local backend

    pending: list[dict] = []
    hype_added = 0
    for chunk, emb in zip(to_embed, embeddings):
        cid = chunk["chunk_id"]
        pending.append({"id": cid, "values": emb, "metadata": _flatten_metadata(chunk)})
        manifest[cid] = {"hash": content_hash(chunk.get("text", "")),
                         "source": chunk.get("metadata", {}).get("source", ""),
                         "version": version or ""}
        if settings.HYPE_ENABLED and chunk.get("metadata", {}).get("chunk_type") in _hype_types():
            try:
                from app.hype import hype_vectors
                hvs = hype_vectors(chunk, settings.HYPE_NUM_QUESTIONS)
                pending.extend(hvs)
                hype_added += len(hvs)
            except Exception as e:
                print(f"[ingest] HyPE generation failed for {cid}: {e}")
        if len(pending) >= batch_size:
            index.upsert(vectors=pending)
            pending = []
    if pending:
        index.upsert(vectors=pending)

    if not reset and plan["to_delete"]:
        index.delete(ids=plan["to_delete"])
        for cid in plan["to_delete"]:
            manifest.pop(cid, None)

    save_manifest(manifest)
    summary["embedded"] = len(embeddings)
    summary["hype_vectors"] = hype_added
    print(f"[ingest] done: {summary}")
    return summary


def _run_ingest_versioned(chunks, manifest, dry_run, batch_size, version) -> dict:
    """Dual-index path: every chunk version is kept; old versions are deactivated
    (metadata update), never deleted. Active vectors carry is_active=True."""
    from app.versioning import plan_versioned, vector_id

    # Numeric epoch timestamps so Pinecone can range-filter validity windows.
    ts = int(version) if version else int(time.time())
    plan, manifest = plan_versioned(chunks, manifest, ts)
    summary = {"total_chunks": len(chunks), "versioned": True, "to_embed": len(plan["to_embed"]),
               "skipped": len(plan["skipped"]), "deactivate": len(plan["deactivate"]), "removed": len(plan["removed"])}
    print(f"[ingest] plan: {summary}")
    if dry_run:
        summary["dry_run"] = True
        return summary

    index = _open_index()
    vectors, embedded = [], 0
    for chunk, ver in plan["to_embed"]:
        cid = chunk["chunk_id"]
        try:
            emb = _embed(chunk.get("text", ""))
        except Exception as e:
            print(f"[ingest] embed failed for {cid}: {e}")
            continue
        meta = _flatten_metadata(chunk)
        # valid_to = OPEN sentinel (far future) so "as of T" range filters match
        # active versions for any T >= valid_from.
        meta.update({"version": ver, "is_active": True, "valid_from": ts, "valid_to": _OPEN_TS})
        vectors.append({"id": vector_id(cid, ver), "values": emb, "metadata": meta})
        if len(vectors) >= batch_size:
            index.upsert(vectors=vectors)
            embedded += len(vectors)
            vectors = []
    if vectors:
        index.upsert(vectors=vectors)
        embedded += len(vectors)

    # Retire prior versions: metadata update only (Phase 4 — never delete).
    for vid in plan["deactivate"]:
        try:
            index.update(id=vid, set_metadata={"is_active": False, "valid_to": ts})
        except Exception as e:
            print(f"[ingest] deactivate {vid} failed: {e}")

    save_manifest(manifest)
    summary["embedded"] = embedded
    summary["deactivated"] = len(plan["deactivate"])
    print(f"[ingest] done: {summary}")
    return summary


if __name__ == "__main__":
    import sys
    run_ingest(dry_run="--dry-run" in sys.argv, reset="--reset" in sys.argv)
