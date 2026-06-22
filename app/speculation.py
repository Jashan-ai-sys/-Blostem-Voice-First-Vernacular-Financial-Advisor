"""
Speculation manager (Phase C) — hides tool latency behind user speech / screen
context by starting SAFE read-only tools early and reusing the result if the
user's final intent matches (else discarding it).

Only safe (read-only) tools are ever speculated — unsafe writes stay locked
behind the Phase B commit point (app/policy.py), so speculation is a pure speedup
with zero safety cost.

Triggers:
  • page/error change  → predict() likely RAG queries from screen + active error
  • partial transcript → /speculate endpoint feeds the user's in-progress words
Reuse:
  • /tools/rag checks reuse() first — a token-overlap match at the CURRENT
    page_version, within TTL, returns the pre-fetched chunks instantly.

Invalidation: entries are scoped to a page_version (navigation invalidates them)
and expire after _SPEC_TTL.
"""
from __future__ import annotations

import re
import time

from app import policy

_SPEC_TTL = 30.0      # seconds a speculation stays valid
_MAX_ENTRIES = 8      # cached speculations per session
_MIN_OVERLAP = 0.5    # Jaccard token-overlap to count as a reuse hit

# session_id -> list[entry];  entry = {query, tokens, page_version, ts, chunks, hits}
_CACHE: dict[str, list[dict]] = {}


def _now() -> float:
    return time.monotonic()


def _tokens(q: str) -> set[str]:
    return {t for t in re.sub(r"[^\w\s]", " ", (q or "").lower()).split() if len(t) > 2}


def _page_version(state) -> int:
    return (getattr(state, "page", None) or {}).get("page_version", 0)


def _prune(sid: str, page_version: int) -> list[dict]:
    """Keep only fresh entries for the current page_version."""
    fresh = [e for e in _CACHE.get(sid, [])
             if e["page_version"] == page_version and (_now() - e["ts"]) < _SPEC_TTL]
    _CACHE[sid] = fresh
    return fresh


def reuse(sid: str, query: str, page_version: int):
    """Return pre-fetched chunks for a query close enough to a live speculation
    at the current page_version — else None (cache miss)."""
    qt = _tokens(query)
    if not qt:
        return None
    best, best_score = None, 0.0
    ql = (query or "").lower()
    for e in _prune(sid, page_version):
        et = e["tokens"]
        if not et:
            continue
        score = len(qt & et) / len(qt | et)
        # substring containment (partial⊂final, or screen-prefixed query) is strong
        if e["query"] and (e["query"] in ql or ql in e["query"]):
            score = max(score, 0.8)
        if score > best_score:
            best, best_score = e, score
    if best and best_score >= _MIN_OVERLAP:
        best["hits"] = best.get("hits", 0) + 1
        return best["chunks"]
    return None


def store(sid: str, query: str, page_version: int, chunks) -> None:
    entries = _CACHE.setdefault(sid, [])
    entries.append({
        "query": (query or "").lower(), "tokens": _tokens(query),
        "page_version": page_version, "ts": _now(), "chunks": chunks, "hits": 0,
    })
    if len(entries) > _MAX_ENTRIES:
        _CACHE[sid] = entries[-_MAX_ENTRIES:]


def predict(state) -> list[str]:
    """Likely safe RAG queries from page + active error — NO transcript needed.
    This is the proactive, screen-driven pre-warm."""
    qs: list[str] = []
    err = getattr(state, "active_error", None) or {}
    for k in ("user_message", "title", "reason", "code"):
        if err.get(k):
            qs.append(str(err[k]))
            break
    screen_id = (getattr(state, "page", None) or {}).get("screen_id") or getattr(state, "screen_id", None)
    if screen_id:
        try:
            from app import screen_graph
            brief = screen_graph.screen_brief(screen_id) or {}
            faqs = brief.get("faqs") or []
            if faqs:
                first = faqs[0]
                qs.append(first.get("q") if isinstance(first, dict) else str(first))
        except Exception:
            pass
    # de-dupe, drop empties, cap
    seen, out = set(), []
    for q in qs:
        q = (q or "").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:2]


def speculate(sid: str, state, queries: list[str] | None = None) -> int:
    """Pre-run SAFE RAG retrieval for predicted/explicit queries → cache.
    Returns how many speculations were actually executed. Blocking (run me in a
    thread from async code). Safe-only: RAG is read-only."""
    if policy.classify("search_financial_rules") != "safe":
        return 0  # defensive: never speculate a non-safe tool
    from app.tool_service import rag_engine

    pv = _page_version(state)
    qlist = queries if queries is not None else predict(state)
    done = 0
    for q in qlist:
        if not q or len(q.strip()) < 4:
            continue
        if reuse(sid, q, pv) is not None:
            continue  # already warm
        try:
            chunks = rag_engine.retrieve_chunks(q)
            store(sid, q, pv, chunks)
            done += 1
        except Exception as e:
            print(f"[spec] retrieve failed for '{q[:40]}': {e}")
    return done


def stats(sid: str) -> dict:
    entries = _CACHE.get(sid, [])
    return {"entries": len(entries), "hits": sum(e.get("hits", 0) for e in entries)}
