from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    query: str
    language: str = "Hinglish" # Options: English, Hindi, Hinglish

class SourceChunk(BaseModel):
    title: str
    text: str
    source_url: Optional[str] = None
    relevance_score: float

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
