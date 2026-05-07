"""
Pydantic models for the Blostem Financial Advisor API.

All request/response schemas live here so main.py stays thin.
"""

from pydantic import BaseModel
from typing import List, Optional


# ─── Legacy Chat Models (used by /ask endpoint if re-enabled) ──────────────

class ChatRequest(BaseModel):
    query: str
    language: str = "Hinglish"  # Options: English, Hindi, Hinglish
    session_id: str = "default_session"

class SourceChunk(BaseModel):
    title: str
    text: str
    source_url: Optional[str] = None
    relevance_score: float

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    latency_seconds: Optional[float] = None
    audio_base64: Optional[str] = None


# ─── Tool Endpoint Request Models ──────────────────────────────────────────

class RAGQuery(BaseModel):
    query: str

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

class ExplainTermQuery(BaseModel):
    term: str
    language: str = "en"


# ─── State Management Models ──────────────────────────────────────────────

class ScreenUpdate(BaseModel):
    step: int
    mode: str = "journey"

class TranscriptMessage(BaseModel):
    role: str   # "user", "bot", or "tool"
    text: str
