"""
Error classification service.
Turns a runtime error (from the SDK / API interceptor) into an actionable,
grounded remedy — the "remedy layer" that maps an IDENTIFIER (code/status) to a
user-facing explanation + suggested action.

Resolution order (most→least specific), per data/error_taxonomy.json:
  1. exact error CODE        (e.g. INVALID_PAN)        → specific remedy
  2. HTTP STATUS fallback    (e.g. 500 → server)       → class remedy
  3. message KEYWORD match   (e.g. "session expired")  → class remedy
  4. unknown fallback                                  → honest generic remedy

Design rule: never fabricate a specific reason. An unknown error gets an honest
class-level remedy, not a made-up cause.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

_TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "error_taxonomy.json")


@lru_cache(maxsize=1)
def _taxonomy() -> dict:
    with open(_TAXONOMY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _result(class_name: str, *, code: str | None, reason: str | None,
            matched_by: str, overrides: dict | None = None) -> dict:
    tax = _taxonomy()
    cls = tax["classes"].get(class_name, tax["classes"]["unknown"])
    overrides = overrides or {}
    return {
        "code": code or None,
        "error_class": class_name,
        "reason": reason or class_name,
        "title": cls["title"],
        "user_message": overrides.get("user_message") or cls["user_message"],
        "suggested_action": overrides.get("suggested_action") or cls["suggested_action"],
        "matched_by": matched_by,
    }


def enrich(classification: dict, screen_id: str | None = None,
           raw_message: str = "", top_k: int = 2) -> list[dict]:
    """Tier-2: pull grounded KB detail for a classified error.

    Searches the BM25 index (LOCAL — no embedding call, no Google quota, instant)
    built from the *classified intent* (title + class + reason + the screen +
    masked message), then keeps only error/concept/screen chunks. Returns up to
    `top_k` {chunk_id, chunk_type, text} for the LLM to ground its answer on.
    Best-effort: returns [] on any failure (the deterministic remedy still stands)."""
    try:
        from app.retrieval import get_bm25_index

        query = " ".join(filter(None, [
            classification.get("title", ""),
            classification.get("error_class", ""),
            classification.get("reason", ""),
            raw_message,
            screen_id or "",
        ]))
        if not query.strip():
            return []

        bm = get_bm25_index()
        wanted = {"error_screen", "concept", "screen"}
        out: list[dict] = []
        for cid in bm.search(query, top_k * 4):
            row = bm.store.get(cid)
            if not row:
                continue
            ctype = (row.get("metadata") or {}).get("chunk_type")
            if ctype in wanted:
                out.append({"chunk_id": cid, "chunk_type": ctype, "text": row["text"][:600]})
            if len(out) >= top_k:
                break
        return out
    except Exception:
        return []


def classify(code: str | None = None, http_status: int | None = None,
             message: str | None = None) -> dict:
    """Resolve an error into {code, error_class, reason, title, user_message,
    suggested_action, matched_by}. Defensive: always returns a usable remedy."""
    try:
        tax = _taxonomy()
        code_n = (code or "").strip().upper()

        # 1) exact code
        if code_n and code_n in tax["codes"]:
            entry = tax["codes"][code_n]
            return _result(entry["class"], code=code_n, reason=entry.get("reason"),
                           matched_by="code", overrides=entry)

        # 2) HTTP status fallback
        if http_status is not None and str(http_status) in tax["status_fallback"]:
            cls = tax["status_fallback"][str(http_status)]
            return _result(cls, code=code_n or None, reason=None,
                           matched_by=f"status:{http_status}")

        # 3) keyword match — specific classes BEFORE generic (network/server), so
        # "session timed out" resolves to session, not network's "timed out".
        text = " ".join(filter(None, [code_n.lower(), (message or "").lower()]))
        if text.strip():
            priority = ["session", "validation", "payment", "permission",
                        "not_found", "rate_limit", "network", "server"]
            for cls_name in priority:
                cls = tax["classes"].get(cls_name, {})
                for kw in cls.get("match", {}).get("keywords", []):
                    if kw in text:
                        return _result(cls_name, code=code_n or None, reason=None,
                                       matched_by=f"keyword:{kw}")

        # 4) honest fallback
        return _result("unknown", code=code_n or None, reason=None, matched_by="fallback")
    except Exception as e:  # never break the request over a classification miss
        return {
            "code": code or None, "error_class": "unknown", "reason": "classify_error",
            "title": "Something didn't go as planned",
            "user_message": "Kuch theek se nahi hua, lekin aapka paisa aur data safe hai.",
            "suggested_action": "Thodi der mein dobara try karein.",
            "matched_by": f"exception:{str(e)[:40]}",
        }
