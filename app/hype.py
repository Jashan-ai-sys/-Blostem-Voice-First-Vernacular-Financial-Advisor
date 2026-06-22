"""HyPE — Hypothetical Prompt Embeddings (index-time technique).

Idea: for each chunk, generate the K questions that chunk *answers*, embed THOSE
questions (as queries), and store them as extra vectors pointing back to the parent
chunk. At search time the user's question matches question↔question — tighter than
question↔passage — and ALL the LLM cost is paid ONCE at ingestion, so there is
**zero added query-time latency**. That property is exactly why HyPE fits a
voice-first app (unlike HyDE, which generates per query).

Integration: `hype_vectors(chunk, n)` returns Pinecone vector dicts whose ids are
`{chunk_id}__hq{i}` but whose metadata carries the PARENT chunk_id + parent text.
The hybrid retriever already fuses on `metadata.chunk_id` and reads `metadata.text`,
so these question-vectors transparently resolve to the parent chunk — no retrieval
code change needed. Multiple hq vectors for one chunk simply reinforce it via RRF.

Cost/quota: question generation needs an LLM per chunk (hundreds of calls for the
corpus). On the Gemini free tier that hits the same 20/day wall that pushed
embeddings local — so this is gated by settings.HYPE_ENABLED (default OFF). Run it
with a billed key or a local LLM.
"""
from __future__ import annotations

import re

from app.config import settings

_PROMPT = (
    "You are building a retrieval index for an Indian fixed-deposit / personal-finance "
    "assistant used in Hindi, Hinglish and English.\n"
    "Given the PASSAGE below, write {n} short, natural questions that a real user could "
    "ask whose answer is found in this passage. Mix English and Hinglish phrasing. "
    "Return ONLY the questions, one per line, no numbering.\n\n"
    "PASSAGE:\n{text}\n"
)


def _parse_questions(text: str, n: int) -> list[str]:
    lines = [re.sub(r"^\s*[\d\.\)\-\*]+\s*", "", ln).strip() for ln in (text or "").splitlines()]
    return [ln for ln in lines if len(ln) > 5][:n]


def _groq_questions(prompt: str, n: int, retries: int = 4) -> list[str]:
    import time

    import requests

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {"model": settings.HYPE_LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4, "max_tokens": 256}
    for attempt in range(retries):
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code == 200:
            return _parse_questions(r.json()["choices"][0]["message"]["content"], n)
        if r.status_code == 429:  # rate limited → back off and retry
            wait = float(r.headers.get("retry-after", 2 * (attempt + 1)))
            time.sleep(min(wait, 15))
            continue
        raise RuntimeError(f"Groq {r.status_code}: {r.text[:200]}")
    raise RuntimeError("Groq rate-limited after retries")


def _gemini_questions(prompt: str, n: int) -> list[str]:
    import google.generativeai as genai

    if settings.GOOGLE_API_KEY:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel(settings.HYPE_LLM_MODEL)
    resp = model.generate_content(prompt)
    return _parse_questions(resp.text or "", n)


def generate_questions(text: str, n: int = 3) -> list[str]:
    """Generate up to n hypothetical questions for a passage via the configured LLM
    (settings.HYPE_LLM_PROVIDER = groq | gemini). Raises on failure so the caller
    logs + skips HyPE for that chunk (HyPE is best-effort enrichment)."""
    prompt = _PROMPT.format(n=n, text=text[:4000])
    if settings.HYPE_LLM_PROVIDER == "groq":
        return _groq_questions(prompt, n)
    return _gemini_questions(prompt, n)


def hype_vectors(chunk: dict, n: int = 3) -> list[dict]:
    """Build hypothetical-question vectors for a chunk. Each carries the PARENT
    chunk_id + text so the hybrid retriever resolves it to the parent automatically.
    Embeds questions as QUERIES (e5 'query:' prefix) for question↔question matching."""
    from app.embedder import embed_texts

    cid = chunk["chunk_id"]
    parent_text = chunk.get("text", "")
    questions = generate_questions(parent_text, n)
    if not questions:
        return []

    vecs = embed_texts(questions, is_query=True)
    meta_src = chunk.get("metadata", {}).get("source", "")
    out: list[dict] = []
    for i, (q, v) in enumerate(zip(questions, vecs)):
        out.append({
            "id": f"{cid}__hq{i}",
            "values": v,
            "metadata": {
                "chunk_id": cid,          # fuse/resolve to the PARENT chunk
                "text": parent_text,      # retriever returns the parent text
                "chunk_type": "hype_question",
                "question": q,
                "source": meta_src,
            },
        })
    return out
