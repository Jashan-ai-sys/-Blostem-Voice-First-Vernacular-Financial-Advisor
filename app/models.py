"""
Pydantic models for the Blostem Financial Advisor API.

All request/response schemas live here so main.py stays thin.
"""

from pydantic import BaseModel
from typing import List, Optional


# ─── Chat / RAG Models (used by /chat and the RAG engine) ──────────────────

class ChatRequest(BaseModel):
    query: str
    language: str = "Hinglish"  # Options: English, Hindi, Hinglish

class SourceChunk(BaseModel):
    title: str
    text: str
    source_url: Optional[str] = None
    relevance_score: float

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]


# ─── Tool Endpoint Request Models ──────────────────────────────────────────

class RAGQuery(BaseModel):
    query: str
    tenant: str | None = None              # per-tenant scoping (overridden by X-Tenant-Id header)
    filters: dict | None = None            # metadata filter, e.g. {"okf_type": "Concept"}

class FDMaturityQuery(BaseModel):
    principal: float
    annual_rate_percent: float
    tenure_years: float
    compounding_frequency: str

class FDRecommendQuery(BaseModel):
    goal_type: str
    liquidity_need: str
    senior_citizen: bool

class IncomeTaxQuery(BaseModel):
    total_income: float
    age: int
    regime: str

class TDSQuery(BaseModel):
    age: int
    fd_interest: float
    pan_available: bool

class UpdateProfileQuery(BaseModel):
    new_cash_amount: float = None
    new_age: int = None
    confirm: bool = False   # commit point: write only after explicit user confirmation

class ExplainTermQuery(BaseModel):
    term: str
    language: str = "en"


# ─── State Management Models ──────────────────────────────────────────────

class ScreenUpdate(BaseModel):
    step: int = 1
    mode: str = "journey"
    screen_id: str | None = None  # exact graph screen (preferred over step)

class ErrorReport(BaseModel):
    """A runtime error the user is seeing, captured by the SDK / API interceptor.
    code/http_status are the IDENTIFIER; the backend maps them to a remedy."""
    code: str | None = None
    message: str | None = None
    http_status: int | None = None
    screen: str | None = None
    field: str | None = None


# ─── Page-aware realtime context (event-driven copilot) ──────────────────────

class FieldError(BaseModel):
    field: str
    code: str

class PageContext(BaseModel):
    """High-signal, structured snapshot of the live screen (NOT raw HTML / no
    screenshot). Streamed by the SDK over the WebSocket on every navigation /
    field-focus / error so the bot is situationally aware of exactly where the
    user is and what's wrong."""
    route: str | None = None
    title: str | None = None
    screen_id: str | None = None          # graph screen id when known
    journey: str | None = None
    step_id: str | None = None
    visible_fields: list[str] = []
    focused_field: str | None = None
    errors: list[FieldError] = []
    primary_cta_enabled: bool | None = None
    page_version: int = 0                  # monotonically increasing per session

class Behavior(BaseModel):
    """Friction signals — let the bot proactively help (rage-clicks → confusion)."""
    idle_seconds: float = 0
    retries: int = 0
    rage_clicks: int = 0
    backtracks: int = 0
    upload_failures: int = 0

class AgentEvent(BaseModel):
    """Envelope for events the SDK pushes over the WebSocket control channel."""
    type: str                              # page_context_update | user_event | voice_partial | voice_final | ui_action_result
    page: PageContext | None = None
    behavior: Behavior | None = None
    text: str | None = None               # voice partial/final transcript
    event: dict | None = None             # arbitrary user_event payload
    action_id: str | None = None
    status: str | None = None

class UIAction(BaseModel):
    """A safe, declarative client action the agent can take (pushed to the SDK
    over the WebSocket). The bot doesn't just talk — it can point at the screen."""
    type: str                              # highlight_field | focus_field | scroll_into_view | show_tooltip | open_help | handoff
    field: str | None = None               # logical field key (resolved via data-field / ui_registry)
    message: str | None = None             # tooltip / help text

class UIActionRequest(BaseModel):
    action: UIAction

class TranscriptMessage(BaseModel):
    role: str   # "user", "bot", or "tool"
    text: str


class VoiceSessionRegister(BaseModel):
    session_id: str
