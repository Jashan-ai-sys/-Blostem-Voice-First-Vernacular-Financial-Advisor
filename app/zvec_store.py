"""
zvec in-memory vector store (local embeddings).
Replaces Pinecone for dense retrieval — an in-process, file-backed vector DB
(Alibaba zvec) with LOCAL sentence-transformer embeddings, so there is NO remote
service and NO Google embedding quota. Dense vectors are computed and searched
entirely on-device.

Embedding model: multilingual (default paraphrase-multilingual-MiniLM-L12-v2) so
Hindi/Hinglish queries cross-match the (English) knowledge chunks. Swap via
ZVEC_EMBED_MODEL. The BM25 layer in retrieval.py covers exact-term matches.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading


def _safe_id(chunk_id: str) -> str:
    """zvec Doc ids have charset/length rules; hash to a safe, collision-free id.
    The real chunk_id is kept in the 'cid' field so retrieval keying is preserved."""
    return hashlib.md5(chunk_id.encode("utf-8")).hexdigest()

from app.config import settings

_ROOT = os.path.dirname(os.path.dirname(__file__))
ZVEC_DIR = os.path.join(_ROOT, "data", "zvec")
COLLECTION = "blostem_chunks"
# Reuse the project's canonical local embedder (multilingual-e5-base, 768d, with
# query:/passage: prefixes) so zvec doc + query vectors match the rest of the system.
EMBED_MODEL = settings.LOCAL_EMBEDDING_MODEL

_colls: dict = {}      # collection name -> open handle (cached)
_lock = threading.RLock()


def _active_collection() -> str:
    """Which collection dense search reads — the contextual variant when the flag
    is on, else the base index. Lets us A/B by flipping CONTEXTUAL_RETRIEVAL."""
    return settings.ZVEC_CONTEXTUAL_COLLECTION if settings.CONTEXTUAL_RETRIEVAL else COLLECTION


def _tenant_slug(tenant: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (tenant or "").lower()).strip("_")[:40]


def _tenant_collection(tenant: str | None) -> str | None:
    """Per-tenant scoping → each tenant's vectors live in their OWN collection
    (true search-space isolation). None/empty → the shared/base collection."""
    if not tenant:
        return None
    return f"{COLLECTION}__{_tenant_slug(tenant)}"


def _match(meta: dict, filters: dict) -> bool:
    """Post-filter: every filter key must match the chunk's metadata. A list value
    means 'membership' (meta value must be one of them)."""
    for k, v in (filters or {}).items():
        mv = meta.get(k)
        if isinstance(v, (list, tuple, set)):
            if mv not in v:
                return False
        elif mv != v:
            return False
    return True


def _dim() -> int:
    return settings.EMBEDDING_DIM


def _embed_doc(text: str) -> list[float]:
    from app import embedder
    return embedder.embed_one(text, is_query=False)   # e5 'passage:' prefix


def _embed_query(text: str) -> list[float]:
    from app import embedder
    return embedder.embed_one(text, is_query=True)     # e5 'query:' prefix


def _path(collection: str | None = None) -> str:
    return os.path.join(ZVEC_DIR, collection or _active_collection())


def _make_query(field: str, vector: list[float]):
    """Build a vector query, tolerating the Query/VectorQuery API across versions."""
    import zvec
    try:
        return zvec.Query(field_name=field, vector=vector)
    except Exception:
        return zvec.VectorQuery(field_name=field, vector=vector)


def build_index(chunks: list[dict], batch_size: int = 200, collection: str | None = None,
                tenant: str | None = None) -> dict:
    """(Re)create the collection and insert all chunks with local embeddings.
    No network, no quota. Target collection precedence: explicit `collection` >
    per-tenant collection (if `tenant`) > base index. Pass `tenant` to build a
    tenant's bundle into its OWN isolated collection."""
    import zvec
    from zvec import CollectionSchema, FieldSchema, VectorSchema, DataType, FlatIndexParam, MetricType, Doc

    coll_name = collection or _tenant_collection(tenant) or COLLECTION
    with _lock:
        if os.path.isdir(_path(coll_name)):
            shutil.rmtree(_path(coll_name), ignore_errors=True)
        os.makedirs(ZVEC_DIR, exist_ok=True)
        try:
            ip = FlatIndexParam(metric_type=MetricType.COSINE)
        except Exception:
            ip = FlatIndexParam()
        schema = CollectionSchema(
            coll_name,
            fields=[FieldSchema("text", DataType.STRING), FieldSchema("meta", DataType.STRING),
                    FieldSchema("cid", DataType.STRING)],
            vectors=[VectorSchema("vec", DataType.VECTOR_FP32, dimension=_dim(), index_param=ip)],
        )
        coll = zvec.create_and_open(_path(coll_name), schema)

        docs, n = [], 0
        for c in chunks:
            cid = c.get("chunk_id")
            if not cid:
                continue
            docs.append(Doc(
                id=_safe_id(cid),
                vectors={"vec": _embed_doc(c.get("text", ""))},
                fields={"text": c.get("text", ""), "cid": cid,
                        "meta": json.dumps(c.get("metadata", {}), ensure_ascii=False)},
            ))
            if len(docs) >= batch_size:
                coll.insert(docs); n += len(docs); docs = []
        if docs:
            coll.insert(docs); n += len(docs)
        coll.flush()
        _colls[coll_name] = coll
        return {"collection": coll_name, "inserted": n, "dim": _dim(), "model": EMBED_MODEL}


def get_collection(collection: str | None = None):
    """Open the on-disk collection (lazy, cached per name). Returns None if not built."""
    coll_name = collection or _active_collection()
    with _lock:
        if _colls.get(coll_name) is None:
            import zvec
            try:
                _colls[coll_name] = zvec.open(_path(coll_name))
            except Exception:
                return None
        return _colls[coll_name]


def query(text: str, top_k: int = 3, tenant: str | None = None,
          filters: dict | None = None, collection: str | None = None) -> list[dict]:
    """Dense search → hits [{id, score, text, metadata}] (cosine similarity, higher
    = better). Search-space scoping:
      • tenant  → search ONLY that tenant's collection (isolation; None = base/active)
      • filters → keep only chunks whose metadata matches (over-fetch + post-filter)
    Returns [] if the index isn't built (caller falls back to BM25)."""
    coll = get_collection(collection or _tenant_collection(tenant))
    if coll is None:
        return []
    fetch_k = top_k * 10 if filters else top_k   # over-fetch so post-filter still fills top_k
    try:
        res = coll.query(queries=[_make_query("vec", _embed_query(text))], topk=fetch_k,
                         output_fields=["text", "meta", "cid"])
    except Exception:
        return []
    hits = []
    for d in res:
        f = d.fields or {}
        meta = {}
        try:
            meta = json.loads(f.get("meta") or "{}")
        except Exception:
            pass
        if filters and not _match(meta, filters):
            continue
        # zvec COSINE returns a distance (lower=closer) → convert to similarity.
        sim = (1.0 - d.score) if d.score is not None else 0.0
        hits.append({"id": f.get("cid") or d.id, "score": sim, "text": f.get("text", ""), "metadata": meta})
        if len(hits) >= top_k:
            break
    return hits
