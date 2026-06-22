"""
Blostem Financial Advisor — FastAPI Backend
============================================
Thin routing layer. Models live in models.py, tools in tool_service.py,
per-session state in memory.py.

Scalability note: all request state is keyed by `session_id` (resolved from the
`X-Session-Id` header) and persisted through the `memory.store` interface. There
is no process-global mutable state, so the app is safe to run multi-user and
multi-worker (set STATE_BACKEND=redis to share state across workers/restarts).
"""

import sys
import io
import os
import asyncio
from collections import deque
from datetime import datetime
from threading import Lock

import shutil

from fastapi import FastAPI, Header, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    ChatRequest, ChatResponse,
    RAGQuery, FDMaturityQuery, FDRecommendQuery,
    IncomeTaxQuery, TDSQuery, UpdateProfileQuery,
    ExplainTermQuery, ScreenUpdate, TranscriptMessage,
    VoiceSessionRegister, ErrorReport, UIActionRequest,
)
from app.memory import store, SessionState
from app.config import settings

# Fix Windows console Unicode — prevents UnicodeEncodeError with Hindi text
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = FastAPI(title="Vernacular Financial Advisor API")

# ─── Session resolution ─────────────────────────────────────────────────────

DEFAULT_SESSION = "default"


def session_id(x_session_id: str | None = Header(default=None)) -> str:
    """Resolve the caller's session from the X-Session-Id header.

    Falls back to a shared "default" session so legacy/unaware clients still
    work — but real clients (frontend + voice agent) always send a unique id.
    """
    return x_session_id or DEFAULT_SESSION


# ─── Voice handshake ────────────────────────────────────────────────────────
# The voice agent is a separate process whose WebRTC connection can't carry our
# app header directly. The frontend registers its session_id as "pending" just
# before opening the voice iframe; the bot claims it on connect. FIFO keeps
# concurrent connects in order. (Replace with URL-param propagation once the
# live Pipecat transport is confirmed to forward query params.)

_PENDING_VOICE: deque[str] = deque(maxlen=64)
_PENDING_LOCK = Lock()

# Live WebSocket connections by session — lets the agent PUSH UI actions to the
# right client (the bot points at the screen, not just talks).
_WS_CLIENTS: dict = {}


# ─── Middleware ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local data folder to serve images directly to the React frontend
if os.path.exists("data"):
    app.mount("/data", StaticFiles(directory="data"), name="data")

# Serve the embeddable widget JS so any host system can include it via one
# <script>. Cross-origin <script src> loads without CORS; the widget's own API
# calls use the CORS policy above. → <script src="{backend}/widget/blostem-widget.js">
_EMBED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "embed")
if os.path.exists(_EMBED_DIR):
    app.mount("/widget", StaticFiles(directory=_EMBED_DIR), name="widget")


# ─── RAG context helper ─────────────────────────────────────────────────────

def _brief_to_text(b: dict) -> str:
    """Flatten a screen_graph brief into the plain text the UI RAG panel shows."""
    lines = [f"Screen: {b['screen']}", b.get("purpose", "")]
    if b.get("do_here"):
        lines.append("What to do: " + b["do_here"])
    if b.get("key_fields"):
        lines.append("Fields: " + "; ".join(b["key_fields"]))
    if b.get("flow"):
        lines.append(b["flow"])
    return "\n".join(l for l in lines if l)


def _populate_rag_context(state: SessionState, query: str, max_sources: int,
                          sid: str | None = None) -> str:
    """Run a RAG query and write image/text context onto the session state.

    If `sid` is given, first try the speculation cache (Phase C): a pre-fetched
    result for the current page_version is reused instantly; otherwise we retrieve
    and warm the cache for repeats. Returns the formatted context string.
    """
    from app.tool_service import rag_engine
    from app import speculation, retrieval_scope

    # The speculation cache is keyed by session+query, NOT by tenant/filter — so a
    # SCOPED query must never serve unscoped cached results (cross-tenant leak).
    # When a tenant/filter scope is active, bypass the cache and retrieve fresh
    # (retrieve_chunks → _dense_search reads the scope and searches the right slice).
    sc = retrieval_scope.current()
    scoped = bool(sc.get("tenant") or sc.get("filters"))

    pv = (state.page or {}).get("page_version", 0)
    sources = None if scoped else (speculation.reuse(sid, query, pv) if sid else None)
    spec_hit = sources is not None
    if sources is None:
        sources = rag_engine.retrieve_chunks(query)
        if sid and not scoped:
            speculation.store(sid, query, pv, sources)
    state.last_rag_spec_hit = spec_hit  # observability: was this a speculation hit?

    state.rag_image = None
    state.rag_text = None

    if sources:
        for s in sources:
            if s.source_url and s.source_url.lower().endswith(('.png', '.jpg', '.jpeg')):
                filename = os.path.basename(s.source_url)
                state.rag_image = f"data/journey_screens/{filename}"
                break
            elif s.source_url and 'http' in s.source_url:
                state.rag_image = s.source_url
                break

    # Cap each chunk: a voice reply is 2-3 sentences, so a smaller tool payload
    # makes the post-tool LLM call faster (lower TTFT) and cheaper (fewer tokens)
    # without hurting answer quality.
    context = "\n\n".join([f"Source: {s.title}\n{s.text[:700]}" for s in sources[:max_sources]])
    if not context.strip():
        context = "No specific rules found in knowledge base."
    state.rag_text = context
    return context


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ═══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE INGESTION (self-serve PDF upload)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/ingest/upload")
def ingest_upload(file: UploadFile = File(...)):
    """Upload a PDF → clean + chunk + index → chat/voice can answer it.

    BM25 makes it searchable immediately; dense vectors are added if API keys
    are configured. Returns a summary of what was ingested.

    Sync `def` (not async) on purpose: extraction (Docling/pypdf) is CPU-bound and
    blocking, so FastAPI runs this in a threadpool — one upload won't freeze the
    event loop / other requests. (Production: move to a background job + job id.)
    """
    from app.ingestion import ingest_pdf_file, run_ingest
    from app.config import settings as _settings

    if not (file.filename or "").lower().endswith(".pdf"):
        return {"error": "Only PDF files are supported."}

    os.makedirs("data/uploads", exist_ok=True)
    dest = os.path.join("data/uploads", os.path.basename(file.filename))
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)

    # Chunk + BM25 index inline (fast, no API) so the doc is searchable now.
    summary = ingest_pdf_file(dest, source_name=file.filename, embed=False)

    # Dense embedding is heavy → run it as a BACKGROUND JOB, never in-request.
    if _settings.UPLOAD_EMBED and _settings.PINECONE_API_KEY and _settings.GOOGLE_API_KEY:
        from app.jobs import runner
        summary["embed_job_id"] = runner.submit(run_ingest, kind="ingest_embed")
        summary["indexed"] = "pending"  # poll GET /ingest/jobs/{id}
    return summary


@app.get("/ingest/jobs/{job_id}")
async def ingest_job_status(job_id: str):
    """Poll the status of a background embedding job."""
    from app.jobs import runner
    return runner.get(job_id) or {"error": "unknown job_id", "status": "not_found"}


# ═══════════════════════════════════════════════════════════════════════════
# SESSION HANDSHAKE (frontend ↔ voice agent)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/session/voice-pending")
async def register_voice_session(req: VoiceSessionRegister):
    """Frontend registers its session_id right before opening the voice iframe."""
    with _PENDING_LOCK:
        _PENDING_VOICE.append(req.session_id)
    return {"status": "ok"}


@app.post("/session/voice-claim")
async def claim_voice_session():
    """Voice agent claims the next pending session on connect."""
    with _PENDING_LOCK:
        sid = _PENDING_VOICE.popleft() if _PENDING_VOICE else DEFAULT_SESSION
    return {"session_id": sid}


# ═══════════════════════════════════════════════════════════════════════════
# TOOL ENDPOINTS (called by voice_agent.py via HTTP)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/tools/rag")
async def raw_rag_search(request: RAGQuery, x_session_id: str | None = Header(default=None),
                         x_tenant_id: str | None = Header(default=None)):
    """Directly queries the RAG index, scoped to a tenant + optional metadata filter."""
    from app.pii_masker import mask_pii
    from app import retrieval_scope
    sid = x_session_id or DEFAULT_SESSION
    state = store.get(sid)
    tenant = x_tenant_id or request.tenant   # header wins; body fallback

    enhanced_query = f"User is on screen: {state.screen}. Query: {mask_pii(request.query)}"
    # Scope the dense search to this tenant's collection + metadata filter.
    with retrieval_scope.scope(tenant=tenant, filters=request.filters):
        context = _populate_rag_context(state, enhanced_query, max_sources=2, sid=sid)  # voice: keep payload small
    store.save(sid, state)

    final_output = (
        f"SYSTEM NOTE - User is currently stuck on: {state.screen}\n\n"
        f"KNOWLEDGE BASE RESULTS:\n{context}"
    )
    return {"results": final_output, "image_path": state.rag_image, "spec_hit": state.last_rag_spec_hit}


@app.post("/tools/fd_maturity")
async def raw_fd_maturity(request: FDMaturityQuery):
    """Calculates FD maturity amount."""
    from app.tool_service import calculate_fd_maturity
    return calculate_fd_maturity.invoke({
        "principal": request.principal,
        "annual_rate_percent": request.annual_rate_percent,
        "tenure_years": request.tenure_years,
        "compounding_frequency": request.compounding_frequency
    })


@app.post("/tools/fd_recommendation")
async def raw_fd_recommendation(request: FDRecommendQuery):
    """Runs the rule-based FD recommendation engine."""
    from app.recommendation_engine import recommend_fd_options
    return recommend_fd_options.invoke({
        "goal_type": request.goal_type,
        "liquidity_need": request.liquidity_need,
        "senior_citizen": request.senior_citizen
    })


@app.post("/tools/income_tax")
async def raw_income_tax(request: IncomeTaxQuery):
    """Calculates income tax for old/new/both regimes."""
    from app.tool_service import calculate_income_tax
    return calculate_income_tax.invoke({
        "total_income": request.total_income,
        "age": request.age,
        "regime": request.regime
    })


@app.post("/tools/tds")
async def raw_tds(request: TDSQuery):
    """Calculates TDS on FD interest."""
    from app.tool_service import calculate_tds_on_fd_interest
    return calculate_tds_on_fd_interest.invoke({
        "age": request.age,
        "fd_interest": request.fd_interest,
        "pan_available": request.pan_available
    })


@app.post("/tools/update_profile")
async def raw_update_profile(request: UpdateProfileQuery, x_session_id: str | None = Header(default=None)):
    """Updates this session's user profile — a STATE-CHANGING (unsafe) tool, so it
    passes the policy COMMIT POINT: nothing is written until the user confirms."""
    from app import policy

    sid = x_session_id or DEFAULT_SESSION
    state = store.get(sid)
    decision = policy.check_commit("update_user_profile", confirmed=request.confirm, state=state)
    if not decision["allow"]:
        print(f"[AUDIT] update_user_profile HELD ({decision['reason']}) sid={sid} args={request.model_dump(exclude={'confirm'})}")
        return {
            "status": "requires_confirmation",
            "requires_confirmation": True,
            "message": "Confirm karein: kya main aapki profile update kar doon? "
                       "(Yes bolne par hi change hoga.)",
        }

    if request.new_cash_amount is not None:
        state.user_profile["cash"] = request.new_cash_amount
    if request.new_age is not None:
        state.user_profile["age"] = request.new_age
        state.user_profile["senior_citizen"] = request.new_age >= 60
    store.save(sid, state)
    print(f"[AUDIT] update_user_profile COMMITTED sid={sid} args={request.model_dump(exclude={'confirm'})}")
    return {"status": "success", "message": "Profile updated for this session."}


@app.post("/tools/explain_term")
async def raw_explain_term(request: ExplainTermQuery):
    """Explains a financial term grounded with RAG context."""
    from app.tool_service import explain_term
    return explain_term.invoke({"term": request.term, "language": request.language})


@app.post("/chat")
async def chat(request: ChatRequest, as_of: str | None = None,
               x_session_id: str | None = Header(default=None)):
    """Text chat. Grounded RAG answer, guardrailed, with citations.

    `?as_of=YYYY-MM-DD` queries the HISTORICAL index — the version of the
    knowledge that was active on that date (requires VERSIONED_INDEX + a
    populated Pinecone index)."""
    from app.tool_service import rag_engine
    from app.pii_masker import mask_pii
    from app.guardrails import apply_guardrails
    sid = x_session_id or DEFAULT_SESSION
    state = store.get(sid)

    as_of_ts = None
    if as_of:
        if not settings.VERSIONED_INDEX:
            return {"reply": "Historical lookup isn't available — the versioned index is off.",
                    "grounded": False, "citations": [], "notes": ["as_of_unavailable"]}
        try:
            as_of_ts = int(datetime.fromisoformat(as_of).timestamp())
        except ValueError:
            return {"reply": "Invalid as_of date. Use YYYY-MM-DD.",
                    "grounded": False, "citations": [], "notes": ["as_of_bad_format"]}

    # Mask Aadhaar/PAN/phone before the query reaches RAG/the LLM.
    safe_query = mask_pii(request.query)

    now = datetime.now().isoformat()
    state.add_message("user", safe_query, now)

    result: ChatResponse = rag_engine.process_query(safe_query, request.language, as_of=as_of_ts)

    # Phase 14/15 gate: refuse if ungrounded; else mask PII, add compliance
    # disclaimer / block abuse, and attach citations.
    guarded = apply_guardrails(result.answer, result.sources, safe_query)
    state.add_message("bot", guarded.text, datetime.now().isoformat())
    store.save(sid, state)

    return {
        "reply": guarded.text,
        "grounded": guarded.grounded,
        "citations": guarded.citations,
        "notes": guarded.notes,
    }


# ═══════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT (Voice Agent ↔ Frontend sync)
# ═══════════════════════════════════════════════════════════════════════════

_STEP_LABELS = {
    1: "Step 1: SIM Binding / Verification",
    2: "Step 2: KYC & Video Verification",
    3: "Step 3: Address Confirmation",
    4: "Step 4: FD Amount & Tenure Selection",
    5: "Step 5: Bank Details Addition",
    6: "Step 6: Nominee Selection",
    7: "Step 7: Final FD Review",
    8: "Step 8: Payment Processing",
    9: "Step 9: Success / Active FD View",
}


@app.post("/state/screen")
async def update_screen(request: ScreenUpdate, x_session_id: str | None = Header(default=None)):
    from app import screen_graph

    sid = x_session_id or DEFAULT_SESSION
    state = store.get(sid)

    if request.mode == "advisor":
        label, screen_id, seq = "Post-Journey Advisor Dashboard", None, None
    elif request.screen_id:
        # Exact graph screen posted by the frontend journey — most precise.
        screen_id = request.screen_id
        pos = screen_graph.position(screen_id)
        label = pos["name"] if pos else request.screen_id
        seq = pos["seq"] if pos else None
    else:
        label = _STEP_LABELS.get(request.step, f"Screen {request.step}")
        screen_id = screen_graph.resolve_step(request.step)
        pos = screen_graph.position(screen_id)
        seq = pos["seq"] if pos else None

    transitioned = state.record_screen(label, screen_id, seq, datetime.utcnow().isoformat())
    pos = screen_graph.position(state.screen_id)
    where = f" ({pos['progress_pct']}% · next: {pos['next_name']})" if pos and pos["next_name"] else ""
    print(f"[{sid}] User is now on: {state.screen}{where}{'' if transitioned else ' (repeat)'}")

    # FAST screen guidance straight from the in-memory graph — O(1), NO embed /
    # Pinecone / BM25. (The dense RAG pipeline is only for free-form Q&A via
    # /chat + search_financial_rules + explain_term.) Screens not in the graph
    # (SIM/Address) just get a generic note — still no network call.
    brief = screen_graph.screen_brief(state.screen_id)
    state.rag_image = None
    state.rag_text = _brief_to_text(brief) if brief else f"You are on: {state.screen}."
    store.save(sid, state)

    return {
        "status": "ok",
        "current_screen": state.screen,
        "screen_id": state.screen_id,
        "position": pos,
    }


@app.post("/state/error")
async def report_error(req: ErrorReport, x_session_id: str | None = Header(default=None)):
    """Capture a runtime error the user is seeing and classify it into an
    actionable remedy. The IDENTIFIER (code/http_status/message) comes from the
    SDK/API interceptor; we map it to a user-facing explanation + suggested step.
    """
    from app import error_service
    from app.pii_masker import mask_pii

    sid = x_session_id or DEFAULT_SESSION
    state = store.get(sid)
    safe_msg = mask_pii(req.message or "")
    remedy = error_service.classify(code=req.code, http_status=req.http_status, message=safe_msg)
    # Tier-2 enrichment: grounded KB detail from BM25 (local, no embed/quota),
    # built from the classified intent + the current screen.
    kb_details = error_service.enrich(remedy, screen_id=state.screen_id, raw_message=safe_msg)
    active = {
        **remedy,
        "screen": req.screen or state.screen,
        "field": req.field,
        "raw_message": safe_msg[:300],
        "http_status": req.http_status,
        "kb_details": kb_details,
        "timestamp": datetime.utcnow().isoformat(),
    }
    state.record_error(active)
    print(f"[{sid}] ERROR on '{active['screen']}': {active['error_class']} "
          f"(via {active['matched_by']}) → {active['suggested_action'][:60]}")
    store.save(sid, state)
    # Speculation (Phase C): pre-warm RAG for the user's likely question about
    # this error, so the bot's explanation comes back with no tool wait.
    asyncio.create_task(_speculate_bg(sid))
    return {"status": "ok", "error": active}


@app.post("/speculate")
async def speculate_partial(request: RAGQuery, x_session_id: str | None = Header(default=None)):
    """Partial-transcript speculation: the voice agent posts the user's
    in-progress words on interim STT frames; we pre-fetch the likely SAFE RAG
    result so the final answer is already warm. Returns immediately."""
    from app import speculation
    sid = x_session_id or DEFAULT_SESSION
    asyncio.create_task(_speculate_bg(sid, queries=[request.query]))
    return {"status": "ok", "stats": speculation.stats(sid)}


async def _speculate_bg(session_id: str, queries: list | None = None):
    """Fire-and-forget: pre-warm SAFE RAG retrieval for the current screen/error
    (or explicit partial-transcript queries) without blocking the caller. The
    blocking retrieval runs in a thread so the event loop stays responsive."""
    from app import speculation
    try:
        state = store.get(session_id)
        n = await asyncio.to_thread(speculation.speculate, session_id, state, queries)
        if n:
            print(f"[spec] pre-warmed {n} for {session_id} ({speculation.stats(session_id)})")
    except Exception as e:
        print(f"[spec] bg error {session_id}: {e}")


@app.websocket("/ws/{session_id}")
async def realtime_ws(ws: WebSocket, session_id: str):
    """Event-driven control channel (page-aware copilot). The SDK pushes
    page_context_update / user_event / voice_* events; we fold them into the
    session store the voice agent already reads — replacing the 1.5s poll with a
    push. This is the foundation the speculation/UI-action layers build on."""
    from app import screen_graph
    await ws.accept()
    _WS_CLIENTS[session_id] = ws
    print(f"[ws] connected: {session_id}")
    try:
        while True:
            raw = await ws.receive_json()
            etype = raw.get("type")
            state = store.get(session_id)

            if etype == "page_context_update":
                page = raw.get("page") or {}
                if state.set_page(page):  # ignores stale (out-of-order) updates
                    sid_graph = page.get("screen_id")
                    if sid_graph:
                        pos = screen_graph.position(sid_graph)
                        label = (pos or {}).get("name") or page.get("title") or sid_graph
                        state.record_screen(label, sid_graph, (pos or {}).get("seq"),
                                            datetime.utcnow().isoformat())
                        brief = screen_graph.screen_brief(sid_graph)
                        state.rag_text = _brief_to_text(brief) if brief else f"You are on: {label}."
                if raw.get("behavior"):
                    state.behavior = raw["behavior"]
                store.save(session_id, state)
                await ws.send_json({"type": "agent_context_ack", "page_version": page.get("page_version", 0)})
                # Speculation (Phase C): pre-warm likely safe RAG for this screen.
                asyncio.create_task(_speculate_bg(session_id))

            elif etype in ("voice_partial", "voice_final"):
                # Transcript events — stored for the (future) speculation lane.
                state.behavior = {**state.behavior, "last_transcript": (raw.get("text") or "")[:200]}
                store.save(session_id, state)

            elif etype == "user_event":
                print(f"[ws] user_event {session_id}: {str(raw.get('event'))[:80]}")

            elif etype == "ui_action_result":
                pass  # ack of a UI action we sent (future UI-action service)
    except WebSocketDisconnect:
        print(f"[ws] disconnected: {session_id}")
    except Exception as e:
        print(f"[ws] error {session_id}: {e}")
    finally:
        if _WS_CLIENTS.get(session_id) is ws:
            _WS_CLIENTS.pop(session_id, None)


@app.post("/state/ui-action")
async def push_ui_action(req: UIActionRequest, x_session_id: str | None = Header(default=None)):
    """The agent pushes a declarative UI action to the user's live client over the
    WebSocket (highlight a field, tooltip, scroll…). Returns delivered=False if no
    socket is connected for this session."""
    sid = x_session_id or DEFAULT_SESSION
    ws = _WS_CLIENTS.get(sid)
    if ws is None:
        return {"status": "ok", "delivered": False}
    try:
        await ws.send_json({"type": "ui_action", "action": req.action.model_dump()})
        return {"status": "ok", "delivered": True}
    except Exception as e:
        _WS_CLIENTS.pop(sid, None)
        return {"status": "error", "delivered": False, "error": str(e)[:80]}


@app.get("/state/get")
async def get_state(x_session_id: str | None = Header(default=None)):
    from app import screen_graph

    sid = x_session_id or DEFAULT_SESSION
    state = store.get(sid)
    pos = screen_graph.position(state.screen_id)
    return {
        "user_state": state.user_profile,
        "current_screen": state.screen,
        "screen_id": state.screen_id,
        "position": pos,
        "flow_guidance": screen_graph.guidance(state.screen_id) if state.screen_id else None,
        "next_screen": pos["next_name"] if pos else None,
        "screen_brief": screen_graph.screen_brief(state.screen_id),
        "active_error": state.active_error,
        "page": state.page,
        "behavior": state.behavior,
        "screen_history": state.screen_history,
        "current_rag_image": state.rag_image,
        "current_rag_text": state.rag_text,
        "conversation": state.conversation,
    }


@app.post("/state/transcript")
async def add_transcript(msg: TranscriptMessage, x_session_id: str | None = Header(default=None)):
    """Receives transcription messages from the voice agent pipeline."""
    from app.pii_masker import mask_pii
    sid = x_session_id or DEFAULT_SESSION
    state = store.get(sid)
    state.add_message(msg.role, mask_pii(msg.text), datetime.now().isoformat())
    store.save(sid, state)
    return {"status": "ok", "total": len(state.conversation)}


@app.post("/state/clear-transcript")
async def clear_transcript(x_session_id: str | None = Header(default=None)):
    """Clears the conversation log (called on new session)."""
    sid = x_session_id or DEFAULT_SESSION
    store.clear_conversation(sid)
    return {"status": "ok"}
