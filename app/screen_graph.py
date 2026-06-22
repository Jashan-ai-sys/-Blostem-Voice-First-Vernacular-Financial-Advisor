"""
Screen Graph Service
====================
Loads the Figma-derived screen knowledge graph (data/figma/screen_graph.json)
once and exposes flow navigation: map a backend step number to a graph screen,
and report where the user is in the journey (position, progress, prev/next).

This is what turns the static graph into live flow-tracking — the backend uses it
in /state/screen to record the user's position and in /state/get + the voice
get_current_screen_context tool to give "you're on step N of M, next is X"
guidance. Pure read-only/derived; no per-session state lives here.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

_GRAPH_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "figma", "screen_graph.json"
)


@lru_cache(maxsize=1)
def _graph() -> dict:
    with open(_GRAPH_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _index() -> dict:
    """Build lookups: screens by id, flow order, and backend-step -> screen id."""
    g = _graph()
    screens = {s["id"]: s for s in g["screens"]}
    flow = g.get("meta", {}).get("flow", [s["id"] for s in g["screens"]])

    # backend step (1..9) -> the primary graph screen (lowest seq) covering it
    step_to_screens: dict[int, list[str]] = {}
    for s in g["screens"]:
        for st in s.get("app_steps_covered", []) or []:
            step_to_screens.setdefault(st, []).append(s["id"])
    step_primary: dict[int, str] = {}
    for st, ids in step_to_screens.items():
        step_primary[st] = min(ids, key=lambda i: screens[i]["seq"])

    return {
        "screens": screens,
        "flow": flow,
        "total": len(flow),
        "step_primary": step_primary,
        "step_to_screens": step_to_screens,
    }


def resolve_step(step: int | None) -> str | None:
    """Map a backend journey step number to its primary graph screen id.

    Returns None for steps with no Figma screen (step 1 SIM, step 3 Address)."""
    if step is None:
        return None
    return _index()["step_primary"].get(step)


def screen_name(screen_id: str | None) -> str | None:
    if not screen_id:
        return None
    s = _index()["screens"].get(screen_id)
    return s["name"] if s else None


def position(screen_id: str | None) -> dict | None:
    """Where this screen sits in the journey: seq, progress %, prev/next.

    Returns None if the screen id isn't in the graph."""
    idx = _index()
    s = idx["screens"].get(screen_id) if screen_id else None
    if not s:
        return None
    seq, total = s["seq"], idx["total"]
    prev_ids, next_ids = s.get("prev", []), s.get("next", [])
    prev_id = prev_ids[0] if prev_ids else None
    next_id = next_ids[0] if next_ids else None
    return {
        "screen_id": s["id"],
        "name": s["name"],
        "app_step": s.get("app_step"),
        "app_step_label": s.get("app_step_label"),
        "seq": seq,
        "total": total,
        "progress_pct": round(seq / total * 100),
        "prev_id": prev_id,
        "prev_name": screen_name(prev_id),
        "next_id": next_id,
        "next_name": screen_name(next_id),
        "is_first": not prev_ids,
        "is_last": not next_ids,
    }


def guidance(screen_id: str | None) -> str:
    """One-line, speakable flow guidance for the voice bot."""
    p = position(screen_id)
    if not p:
        return "I couldn't place this screen in the booking flow."
    parts = [f"You're on '{p['name']}', step {p['seq']} of {p['total']} ({p['progress_pct']}% through)."]
    if p["next_name"]:
        parts.append(f"Next is '{p['next_name']}'.")
    else:
        parts.append("This is the final step.")
    return " ".join(parts)


def screen_brief(screen_id: str | None) -> dict | None:
    """Rich, curated screen guidance straight from the in-memory graph — an O(1)
    lookup, NO embedding / Pinecone / BM25. This is the fast path for
    get_current_screen_context: structured help is more accurate than a retrieved
    chunk and ~1000x faster. Returns None if the screen isn't in the graph."""
    s = _index()["screens"].get(screen_id) if screen_id else None
    if not s:
        return None
    return {
        "screen": s["name"],
        "purpose": s.get("purpose", ""),
        "do_here": s.get("what_user_does", ""),
        "key_fields": [f"{f['label']}: {f['desc']}" for f in s.get("fields", [])[:6]],
        "faqs": [{"q": q["q"], "a": q["a"]} for q in s.get("faqs", [])[:3]],
        "flow": guidance(screen_id),
    }
