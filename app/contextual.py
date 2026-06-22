"""
Contextual Retrieval (Anthropic technique) — index-time chunk augmentation.

Problem: an isolated chunk often loses what it refers to — e.g. a child chunk
"…senior citizens get an extra 0.5% p.a." doesn't say WHICH product/section, so
it embeds/searches poorly. Fix: before embedding, prepend a 1-line, LLM-generated
context that situates the chunk inside its document. Anthropic report this cuts
retrieval failures substantially. All LLM cost is paid ONCE at ingest → ZERO
added query latency (same property that makes HyPE voice-friendly; see [[hype]]).

This is an A/B PROTOTYPE: it builds a SEPARATE zvec collection
(settings.ZVEC_CONTEXTUAL_COLLECTION) so the live base index is never touched.
Flip settings.CONTEXTUAL_RETRIEVAL to route queries to it.

Cost/quota: one LLM call per chunk at ingest. Defaults to Groq
(settings.CONTEXTUAL_LLM_PROVIDER) to stay off the Gemini free-tier wall.
"""
from __future__ import annotations

import time

from app.config import settings

# Anthropic's situating-context prompt, adapted for Indian FD / personal-finance.
_PROMPT = (
    "You are indexing documents for a Hindi/Hinglish/English fixed-deposit & "
    "personal-finance assistant.\n"
    "<document>\n{doc}\n</document>\n\n"
    "Here is a chunk from that document:\n<chunk>\n{chunk}\n</chunk>\n\n"
    "Write a SHORT (max 1 sentence) context that situates this chunk within the "
    "document — name the product/section/topic it belongs to so it can be found "
    "by search. Answer with ONLY the context sentence, nothing else."
)


def _groq_complete(prompt: str, retries: int = 4) -> str:
    import requests

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {"model": settings.CONTEXTUAL_LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2, "max_tokens": 80}
    for attempt in range(retries):
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code == 200:
            return (r.json()["choices"][0]["message"]["content"] or "").strip()
        if r.status_code == 429:
            time.sleep(min(float(r.headers.get("retry-after", 2 * (attempt + 1))), 15))
            continue
        raise RuntimeError(f"Groq {r.status_code}: {r.text[:200]}")
    raise RuntimeError("Groq rate-limited after retries")


def _gemini_complete(prompt: str) -> str:
    import google.generativeai as genai

    if settings.GOOGLE_API_KEY:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel(settings.CONTEXTUAL_LLM_MODEL)
    return (model.generate_content(prompt).text or "").strip()


def _complete(prompt: str) -> str:
    if settings.CONTEXTUAL_LLM_PROVIDER == "gemini":
        return _gemini_complete(prompt)
    return _groq_complete(prompt)


def _doc_context(source: str, by_source: dict[str, list[dict]]) -> str:
    """Compact 'document' to situate chunks against: the source's PARENT texts
    (children are sub-parts), truncated to a budget so the prompt stays cheap."""
    parents = [c.get("text", "") for c in by_source.get(source, [])
               if c.get("metadata", {}).get("chunk_type") != "child"]
    doc = "\n\n".join(parents) or "\n\n".join(c.get("text", "") for c in by_source.get(source, []))
    return doc[: settings.CONTEXTUAL_DOC_BUDGET]


def contextualize_chunks(chunks: list[dict], log_every: int = 50) -> list[dict]:
    """Return NEW chunks whose `text` is `"<context>\\n\\n<original>"`. Best-effort:
    on any LLM failure the original text is kept (no context), so a flaky call never
    drops a chunk. Original text is preserved in metadata.raw_text for inspection."""
    by_source: dict[str, list[dict]] = {}
    for c in chunks:
        by_source.setdefault(c.get("metadata", {}).get("source", "?"), []).append(c)

    out: list[dict] = []
    failures = 0
    for i, c in enumerate(chunks):
        src = c.get("metadata", {}).get("source", "?")
        raw = c.get("text", "")
        ctx = ""
        try:
            ctx = _complete(_PROMPT.format(doc=_doc_context(src, by_source), chunk=raw[:2000]))
        except Exception as e:
            failures += 1
            if failures <= 5:
                print(f"[contextual] skip {c.get('chunk_id')}: {e}")
        new = dict(c)
        new_meta = dict(c.get("metadata", {}))
        new_meta["raw_text"] = raw
        new_meta["contextualized"] = bool(ctx)
        new["metadata"] = new_meta
        new["text"] = f"{ctx}\n\n{raw}" if ctx else raw
        out.append(new)
        if (i + 1) % log_every == 0:
            print(f"[contextual] {i + 1}/{len(chunks)} done ({failures} failed)")
    print(f"[contextual] complete: {len(out)} chunks, {failures} without context")
    return out
