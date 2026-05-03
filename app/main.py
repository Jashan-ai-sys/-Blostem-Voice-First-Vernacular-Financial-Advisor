from fastapi import FastAPI
from app.models import ChatRequest, ChatResponse
from app.rag import RAGEngine

app = FastAPI(title="Vernacular Financial Advisor API")
rag_engine = RAGEngine()

@app.on_event("startup")
async def startup_event():
    # Initialize connections on startup
    rag_engine.initialize()

@app.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Accepts a user query and language, retrieves relevant context,
    and returns a grounded answer with sources.
    """
    response = rag_engine.process_query(request.query, request.language)
    return response

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
