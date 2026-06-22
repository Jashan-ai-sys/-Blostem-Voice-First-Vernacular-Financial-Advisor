"""
Retrieval Service — Hybrid search + reranking
=============================================
Wave-2 retrieval quality layer. Pipeline:

    dense (Pinecone)  ┐
                      ├─ Reciprocal Rank Fusion ─→ rerank ─→ parent expansion
    sparse (BM25)     ┘

Why hybrid: dense vectors win on semantic/paraphrase queries ("how do refunds
work"); BM25 wins on exact tokens (IFSC codes, form numbers like "Form 39",
"194A", "DICGC"). Fusing both beats either alone.

Stages are config-gated (see app/config.py) and the reranker is pluggable, so a
production cross-encoder / hosted reranker can replace the default with no caller
changes. Dense search is injected by the RAG engine to avoid an import cycle.
"""

from __future__ import annotations

import json
import os
import re
from typing import Callable, Protocol

from app.config import settings
from app.models import SourceChunk

_CHUNKS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "chunks", "retrieval_chunks.jsonl"
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# ─── Fusion ──────────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Combine multiple ranked id lists into one. Position-based, score-agnostic
    (so dense cosine and BM25 scores never need normalizing). Returns
    (chunk_id, fused_score) sorted best-first."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


# ─── Sparse (BM25) ───────────────────────────────────────────────────────────

class BM25Index:
    """Keyword search over the local chunk corpus. Built once at startup; needs
    no external service, so it works offline and is fully unit-testable."""

    def __init__(self, chunks_path: str = _CHUNKS_PATH, chunks: list[dict] | None = None):
        self.store: dict[str, dict] = {}
        self.ids: list[str] = []
        corpus_tokens: list[list[str]] = []

        # `chunks` (the assembled corpus: docs + OKF) takes precedence; otherwise
        # read the raw jsonl file (default — keeps tests/back-compat unchanged).
        if chunks is None:
            chunks = []
            if os.path.exists(chunks_path):
                with open(chunks_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            chunks.append(json.loads(line))

        for chunk in chunks:
            cid = chunk.get("chunk_id")
            if not cid:
                continue
            text = chunk.get("text", "")
            self.store[cid] = {"text": text, "metadata": chunk.get("metadata", {})}
            self.ids.append(cid)
            corpus_tokens.append(_tokenize(text))

        self._bm25 = None
        if corpus_tokens:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(corpus_tokens)

    def search(self, query: str, top_k: int) -> list[str]:
        if not self._bm25 or not self.ids:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.ids[i] for i in ranked[:top_k] if scores[i] > 0]


# ─── Reranking (pluggable) ───────────────────────────────────────────────────

class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[SourceChunk], top_k: int) -> list[SourceChunk]: ...


class NoOpReranker:
    """Keeps fusion order. Default — adds zero latency."""

    def rerank(self, query: str, chunks: list[SourceChunk], top_k: int) -> list[SourceChunk]:
        return chunks[:top_k]


class LLMReranker:
    """Pointwise LLM relevance reranker (Gemini). Higher quality, but adds a
    model call per query — flip RERANK_ENABLED on only when you accept that
    latency, or swap in a cross-encoder / hosted reranker here."""

    def __init__(self, model: str):
        self.model = model

    def rerank(self, query: str, chunks: list[SourceChunk], top_k: int) -> list[SourceChunk]:
        try:
            import google.generativeai as genai

            listing = "\n".join(f"[{i}] {c.text[:500]}" for i, c in enumerate(chunks))
            prompt = (
                "Rank the passages by relevance to the query. "
                "Return ONLY a comma-separated list of passage numbers, most relevant first.\n\n"
                f"Query: {query}\n\nPassages:\n{listing}"
            )
            resp = genai.GenerativeModel(self.model).generate_content(prompt)
            order = [int(x) for x in re.findall(r"\d+", resp.text)]
            seen: set[int] = set()
            ranked: list[SourceChunk] = []
            for i in order:
                if 0 <= i < len(chunks) and i not in seen:
                    ranked.append(chunks[i])
                    seen.add(i)
            for i, c in enumerate(chunks):  # append any the model dropped
                if i not in seen:
                    ranked.append(c)
            return ranked[:top_k]
        except Exception as e:
            print(f"Rerank error: {e}")
            return chunks[:top_k]


# ─── Orchestrator ────────────────────────────────────────────────────────────

# Dense search returns dicts: {"id", "score", "text", "metadata"}. Optional
# third arg `as_of` (epoch int) selects the historical version window.
DenseSearch = Callable[..., list[dict]]


class HybridRetriever:
    def __init__(self, dense_search: DenseSearch, bm25: BM25Index | None = None,
                 reranker: Reranker | None = None):
        self.dense_search = dense_search
        self._bm25 = bm25  # None → resolve the live singleton so reloads are picked up
        self.reranker = reranker if reranker is not None else _default_reranker()

    @property
    def bm25(self) -> "BM25Index":
        return self._bm25 if self._bm25 is not None else get_bm25_index()

    def retrieve(self, query: str, top_k: int = 3, as_of: int | None = None) -> list[SourceChunk]:
        fetch_k = max(top_k * settings.RETRIEVAL_FETCH_MULTIPLIER, top_k)

        # Historical "as of" → dense-only. BM25 indexes only the current corpus
        # text, so it can't serve past versions; Pinecone holds the full history.
        if as_of is not None:
            dense_hits = self.dense_search(query, fetch_k, as_of)
            candidates = [self._to_source_chunk(h["id"], h, expand=False) for h in dense_hits]
            candidates = [c for c in candidates if c is not None]
            if settings.RERANK_ENABLED and candidates:
                return self.reranker.rerank(query, candidates, top_k)
            return candidates[:top_k]

        mode = settings.RETRIEVAL_MODE

        dense_hits = self.dense_search(query, fetch_k) if mode in ("dense", "hybrid") else []
        dense_by_id = {h["id"]: h for h in dense_hits}
        dense_ids = [h["id"] for h in dense_hits]
        sparse_ids = self.bm25.search(query, fetch_k) if mode in ("sparse", "hybrid") else []

        if mode == "dense":
            fused_ids = dense_ids
            if not fused_ids:
                # Dense empty (Pinecone unreachable / embedder failed to load) →
                # BM25 safety net so voice keeps answering instead of going blank.
                fused_ids = self.bm25.search(query, fetch_k)
        elif mode == "sparse":
            fused_ids = sparse_ids
        else:
            fused_ids = [cid for cid, _ in reciprocal_rank_fusion([dense_ids, sparse_ids], settings.RRF_K)]

        candidates = [self._to_source_chunk(cid, dense_by_id.get(cid)) for cid in fused_ids[:fetch_k]]
        candidates = [c for c in candidates if c is not None]

        if settings.RERANK_ENABLED and candidates:
            return self.reranker.rerank(query, candidates, top_k)
        return candidates[:top_k]

    def _to_source_chunk(self, cid: str, dense_hit: dict | None, expand: bool = True) -> SourceChunk | None:
        local = self.bm25.store.get(cid)
        if dense_hit is not None:
            text = dense_hit.get("text") or (local["text"] if local else "")
            meta = dense_hit.get("metadata") or (local["metadata"] if local else {})
            score = float(dense_hit.get("score", 0.0))
        elif local is not None:
            text, meta, score = local["text"], local["metadata"], 0.0
        else:
            return None

        # Parent-context expansion: a child chunk is precise for matching but thin
        # for the LLM — swap in the fuller parent text (available locally).
        if expand and settings.CONTEXT_EXPANSION and meta.get("chunk_type") == "child":
            parent_id = meta.get("parent_id")
            parent = self.bm25.store.get(parent_id) if parent_id else None
            if parent:
                text = parent["text"]

        title = (meta.get("title") or meta.get("section") or meta.get("screen_title")
                 or meta.get("question_id") or "Extracted Chunk")
        source_url = meta.get("image_path") or meta.get("source") or ""
        return SourceChunk(title=title, text=text, source_url=source_url, relevance_score=score)


def _default_reranker() -> Reranker:
    if settings.RERANK_ENABLED:
        return LLMReranker(settings.RERANK_MODEL)
    return NoOpReranker()


# Module-level BM25 singleton (corpus loaded once).
_BM25_SINGLETON: BM25Index | None = None


def _assembled_corpus() -> list[dict]:
    """Docs + OKF (screen/concept/error source of truth), minus legacy screen_graph."""
    from app.ingestion import load_index_corpus
    return load_index_corpus()


def get_bm25_index() -> BM25Index:
    global _BM25_SINGLETON
    if _BM25_SINGLETON is None:
        _BM25_SINGLETON = BM25Index(chunks=_assembled_corpus())
    return _BM25_SINGLETON


def reload_bm25_index() -> BM25Index:
    """Rebuild the BM25 index from the corpus (docs + OKF) so newly added chunks /
    edited OKF concepts are immediately searchable without a restart."""
    global _BM25_SINGLETON
    _BM25_SINGLETON = BM25Index(chunks=_assembled_corpus())
    return _BM25_SINGLETON
