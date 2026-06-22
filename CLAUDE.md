# CLAUDE.md — Blostem Voice Advisor

Project-level notes for this repo. The global `~/.claude/CLAUDE.md` engineering
standards still apply; this file adds what's specific to THIS codebase.

## What this is
A Hindi/vernacular, voice-first Fixed-Deposit advisor: a **page-aware, realtime
voice copilot** over an FD onboarding journey, with a local RAG knowledge base.
Backend = FastAPI (`app/`), voice = pipecat (`voice_agent.py`), frontend =
Next.js (`YieldWise/frontend/`).

## Run / dev (Windows, from repo root, in `.venv`)
- **Backend** (`:8000`): `uvicorn app.main:app --reload`
- **Voice agent** (`:7860`): `python voice_agent.py -t webrtc`
- **Frontend** (`:3000`): `cd YieldWise/frontend && npm run dev`
- **Build the vector index** (local, no quota): `python scripts/build_zvec_index.py`
- Tests: `pytest tests/`  ·  Frontend type-check: `npx tsc --noEmit`

## Models / stack (configured in `app/config.py` + `.env`)
- **Voice mode** is the `VOICE_MODE` flag in `.env`:
  - `cascaded` (default in code): **Sarvam Saarika v2.5** STT → **Gemini 2.5 Flash** (text) → **Cartesia Sonic-3.5** TTS. Has the PII guardrail, latency filler, and partial-transcript speculation.
  - `gemini_live`: one audio-native model (**Gemini Live**) does STT+LLM+TTS. NO PII guardrail (no text checkpoint), no filler, and partial-transcript speculation does NOT fire (no Sarvam interim frames).
- **Embeddings**: LOCAL `intfloat/multilingual-e5-base` (768d) via `app/embedder.py` — `query:`/`passage:` prefixes. NOT the Gemini embedding API (off-quota, Hinglish-robust).
- **Vector DB**: **zvec**, local in-memory (`app/zvec_store.py`), default `VECTOR_BACKEND=zvec` (`pinecone` still available). Index lives at `data/zvec/`.
- **Retrieval**: dense-only (`RETRIEVAL_MODE=dense`); BM25 is a fallback when dense is empty. Reranker + HyPE are OFF.
- **The only cloud quota dependency in the hot path is the Gemini LLM** (AI Studio free tier ≈ 20 generate_content/day — bill the project for real use). Embeddings + vector search are 100% local.

## Architecture — the page-aware realtime copilot
Transport is split: **WebRTC for audio**, **WebSocket for control/context**.
- **WebSocket `/ws/{session_id}`** ([app/main.py](app/main.py)) carries `PageContext` (route, fields, focused_field, errors, behavior, page_version) + events. Replaces polling with a push into the same session store the voice agent reads.
- **Phase A — UI actions**: the agent can point at the screen. `highlight_field` tool → `POST /state/ui-action` → pushed over the WS → frontend resolves `[data-field="<key>"]` and highlights it.
- **Phase B — policy / commit point** ([app/policy.py](app/policy.py)): tools are `safe` (read) vs `unsafe` (write); **default-deny**. Unsafe writes (e.g. `update_user_profile`) are HELD until explicit confirmation (`confirm=true`); `[AUDIT]` logs each decision.
- **Phase C — speculation** ([app/speculation.py](app/speculation.py)): pre-fetches SAFE RAG on navigation / error / partial transcript, scoped to `page_version` + 30s TTL; `/tools/rag` reuses it (`spec_hit`). Only safe tools are ever speculated.

## State / cache
- Session state goes through `app/memory.py` (`StateStore`). Currently `STATE_BACKEND=memory` (in-process dict, wiped on restart, per-process). `RedisStore` is wired — flip `STATE_BACKEND=redis` for shared/persistent state.
- Speculation cache + WS client registry are in-process RAM (not Redis yet).

## Conventions / rules (IMPORTANT)
- **Secrets**: API keys live in `.env` (gitignored) only. NEVER hardcode keys in source. Advise rotation if a key is pasted in plaintext.
- **Process kills must be SURGICAL**: kill the specific PID/tree by port or command-line (uvicorn / `voice_agent.py`). NEVER "kill all python". On Windows, tree-kill with `taskkill /PID <root> /T /F` after verifying the command line.
- **Fintech**: NO screenshots. Runtime screen context must be structured text (PageContext), PII-masked (`app/pii_masker.py`).
- The voice agent and backend are **separate processes** that share state only via the backend session store (HTTP/WS) — not in-memory.

## Gotchas
- **Cold model load**: the first RAG call after a backend start loads e5-base + opens zvec (can take >10s). Subsequent calls are fast. Consider a boot warm-up if first-turn latency matters.
- **Windows orphan sockets**: a dead process's inherited handle can keep `:8000`/`:7860` bound — kill the specific child/tree, then re-check the port.
- **Do NOT delete `data/zvec/.../idmap.0/*.log`** — those are zvec's internal index files, not app logs.
- `app/main.py` resolves `VECTOR_BACKEND` via `getattr(settings, "VECTOR_BACKEND", "zvec")` (default zvec even if unset).
