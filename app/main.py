"""
Blostem Financial Advisor — FastAPI Backend
============================================
Thin routing layer. All models live in models.py, all tools in tool_service.py.
"""

import sys
import io
import os
from datetime import datetime
from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.models import (
    ChatRequest, ChatResponse,
    RAGQuery, FDMaturityQuery, FDRecommendQuery,
    IncomeTaxQuery, TDSQuery, UpdateProfileQuery,
    ExplainTermQuery, ScreenUpdate, TranscriptMessage,
)

# Fix Windows console Unicode — prevents UnicodeEncodeError with Hindi text
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = FastAPI(title="Vernacular Financial Advisor API")

# ─── Global Demo State ─────────────────────────────────────────────────────

CURRENT_SCREEN_STATE = "Step 1: Mobile Verification Screen"
CURRENT_RAG_IMAGE = None
CURRENT_RAG_TEXT = None
CONVERSATION_LOG = []  # [{"role": "user"|"bot"|"tool", "text": "...", "timestamp": "..."}]
DEMO_USER_STATE = {
    "age": 65,
    "senior_citizen": True,
    "cash": 500000.0,
    "language": "hinglish"
}

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


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ═══════════════════════════════════════════════════════════════════════════
# TOOL ENDPOINTS (called by voice_agent.py via HTTP)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/tools/rag")
async def raw_rag_search(request: RAGQuery):
    """Directly queries the Pinecone RAG index."""
    from app.tool_service import rag_engine
    global CURRENT_RAG_IMAGE, CURRENT_RAG_TEXT

    enhanced_query = f"User is on screen: {CURRENT_SCREEN_STATE}. Query: {request.query}"
    sources = rag_engine.retrieve_chunks(enhanced_query)

    CURRENT_RAG_IMAGE = None
    CURRENT_RAG_TEXT = None

    if sources:
        for s in sources:
            if s.source_url and (s.source_url.endswith('.png') or s.source_url.endswith('.jpg') or s.source_url.endswith('.jpeg')):
                filename = os.path.basename(s.source_url)
                CURRENT_RAG_IMAGE = f"data/journey_screens/{filename}"
                break
            elif s.source_url and 'http' in s.source_url:
                CURRENT_RAG_IMAGE = s.source_url
                break

    context = "\n\n".join([f"Source: {s.title}\n{s.text}" for s in sources[:3]])
    if not context.strip():
        context = "No specific rules found in knowledge base."

    CURRENT_RAG_TEXT = context

    final_output = f"SYSTEM NOTE - User is currently stuck on: {CURRENT_SCREEN_STATE}\n\nKNOWLEDGE BASE RESULTS:\n{context}"
    return {
        "results": final_output,
        "image_path": CURRENT_RAG_IMAGE
    }


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
async def raw_update_profile(request: UpdateProfileQuery):
    """Updates the global user state."""
    global DEMO_USER_STATE
    if request.new_cash_amount is not None:
        DEMO_USER_STATE["cash"] = request.new_cash_amount
    if request.new_age is not None:
        DEMO_USER_STATE["age"] = request.new_age
        DEMO_USER_STATE["senior_citizen"] = request.new_age >= 60
    return {"status": "success", "message": "State updated locally in the backend."}


@app.post("/tools/explain_term")
async def raw_explain_term(request: ExplainTermQuery):
    """Explains a financial term grounded with RAG context."""
    from app.tool_service import explain_term
    return explain_term.invoke({"term": request.term, "language": request.language})


# ═══════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT (Voice Agent ↔ Frontend sync)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/state/screen")
async def update_screen(request: ScreenUpdate):
    global CURRENT_SCREEN_STATE

    if request.mode == "advisor":
        CURRENT_SCREEN_STATE = "Post-Journey Advisor Dashboard"
    else:
        step_map = {
            1: "Step 1: SIM Binding / Verification",
            2: "Step 2: KYC & Video Verification",
            3: "Step 3: Address Confirmation",
            4: "Step 4: FD Amount & Tenure Selection",
            5: "Step 5: Bank Details Addition",
            6: "Step 6: Nominee Selection",
            7: "Step 7: Final FD Review",
            8: "Step 8: Payment Processing",
            9: "Step 9: Success / Active FD View"
        }
        CURRENT_SCREEN_STATE = step_map.get(request.step, f"Screen {request.step}")

    print(f"User is now on: {CURRENT_SCREEN_STATE}")

    # Auto-fetch RAG context for the new screen so the UI populates immediately
    global CURRENT_RAG_IMAGE, CURRENT_RAG_TEXT
    from app.tool_service import rag_engine
    import os
    
    # Query Pinecone specifically for this screen's context
    enhanced_query = f"User is on screen: {CURRENT_SCREEN_STATE}"
    sources = rag_engine.retrieve_chunks(enhanced_query)
    
    CURRENT_RAG_IMAGE = None
    CURRENT_RAG_TEXT = None

    if sources:
        for s in sources:
            if s.source_url and (s.source_url.endswith('.png') or s.source_url.endswith('.jpg') or s.source_url.endswith('.jpeg')):
                filename = os.path.basename(s.source_url)
                CURRENT_RAG_IMAGE = f"data/journey_screens/{filename}"
                break
            elif s.source_url and 'http' in s.source_url:
                CURRENT_RAG_IMAGE = s.source_url
                break

        context = "\n\n".join([f"Source: {s.title}\n{s.text}" for s in sources[:2]])
        CURRENT_RAG_TEXT = context if context.strip() else "No specific rules found in knowledge base."

    return {"status": "ok", "current_screen": CURRENT_SCREEN_STATE}


@app.get("/state/get")
async def get_state():
    return {
        "user_state": DEMO_USER_STATE,
        "current_screen": CURRENT_SCREEN_STATE,
        "current_rag_image": CURRENT_RAG_IMAGE,
        "current_rag_text": CURRENT_RAG_TEXT,
        "conversation": CONVERSATION_LOG,
    }


@app.post("/state/transcript")
async def add_transcript(msg: TranscriptMessage):
    """Receives transcription messages from the voice agent pipeline."""
    CONVERSATION_LOG.append({
        "role": msg.role,
        "text": msg.text,
        "timestamp": datetime.now().isoformat(),
    })
    # Keep only last 50 messages to prevent memory issues
    if len(CONVERSATION_LOG) > 50:
        CONVERSATION_LOG.pop(0)
    return {"status": "ok", "total": len(CONVERSATION_LOG)}


@app.post("/state/clear-transcript")
async def clear_transcript():
    """Clears the conversation log (called on new session)."""
    CONVERSATION_LOG.clear()
    return {"status": "ok"}
