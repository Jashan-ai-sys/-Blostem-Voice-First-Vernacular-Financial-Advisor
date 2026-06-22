from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "financial-knowledge"
    GENERATION_MODEL: str = "gemini-2.5-flash"
    SARVAM_API_KEY: str = ""

    # ─── Embeddings ──────────────────────────────────────────────────────────
    # Decision 2026-06-18: embeddings run on a LOCAL multilingual model, off the
    # Gemini API — ~10x faster (52ms vs 524ms), no free-tier quota wall, and
    # Hinglish-robust (English-only models collapsed on Hindi queries; see
    # scripts/eval_embedding_accuracy.py). "local" = e5-base; "gemini" = legacy API.
    EMBEDDING_BACKEND: str = "local"                      # local | gemini
    LOCAL_EMBEDDING_MODEL: str = "intfloat/multilingual-e5-base"  # 768-dim, multilingual
    LOCAL_EMBEDDING_BATCH: int = 32
    EMBEDDING_DEVICE: str = "cpu"    # auto|cuda|cpu — pinned to CPU (no GPU build)
    EMBEDDING_DIM: int = 768                              # must match the Pinecone index
    EMBEDDING_MODEL: str = "models/gemini-embedding-2"    # only used when BACKEND=gemini

    # ─── HyPE — Hypothetical Prompt Embeddings (index-time) ──────────────────
    # For each chunk, generate K hypothetical questions it answers, embed THOSE as
    # queries, and store them as extra vectors → query↔question matching at search
    # time with ZERO added query latency (all LLM cost paid once at ingestion).
    # Generation runs on Groq (fast, free-ish) — provider "groq" uses GROQ_API_KEY;
    # "gemini" uses GOOGLE_API_KEY. Only NON-child chunks get HyPE (children are
    # sub-parts of parents) to keep the LLM-call count down.
    HYPE_ENABLED: bool = False   # tested + wired (Groq gpt-oss-120b); enable to populate the corpus
    HYPE_NUM_QUESTIONS: int = 3
    HYPE_LLM_PROVIDER: str = "groq"                 # groq | gemini
    HYPE_LLM_MODEL: str = "openai/gpt-oss-120b"     # enabled at org level on this Groq key
    HYPE_CHUNK_TYPES: str = "parent,screen,concept,error_screen"
    GROQ_API_KEY: str = ""

    # ─── Cascaded voice (STT/TTS) ────────────────────────────────────────────
    SARVAM_STT_MODEL: str = "saarika:v2.5"
    CARTESIA_API_KEY: str = ""
    CARTESIA_VOICE_ID: str = ""
    CARTESIA_MODEL: str = "sonic-3"

    # ─── Session state backend ───────────────────────────────────────────────
    # "memory" (default, in-process, lost on restart) or "redis" (multi-worker,
    # survives restart). Flip via env to scale out — no code changes needed.
    STATE_BACKEND: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_TTL_SECONDS: int = 1800  # 30 min idle expiry for Redis sessions

    # ─── Ingestion / extraction ──────────────────────────────────────────────
    # "docling" = structured extraction + OCR for scanned PDFs (heavier, downloads
    # models on first run). "pypdf" = lightweight text-only fallback.
    PDF_EXTRACTOR: str = "docling"
    # Whether /ingest/upload embeds to Pinecone inline. Default False: upload makes
    # the doc BM25-searchable immediately (fast, no quota), and dense vectors are
    # added out-of-band via `python scripts/ingest_pinecone.py`. Embedding a whole
    # corpus inside an HTTP request would block and exhaust API quota.
    UPLOAD_EMBED: bool = False
    # Dual active/historical index (Phase 7). Off = simple single-version upsert.
    # On = every chunk version kept; retrieval filters is_active; history preserved.
    VERSIONED_INDEX: bool = False

    # ─── Retrieval (Wave 2) ──────────────────────────────────────────────────
    # dense | sparse | hybrid. Default DENSE since the e5-local migration (2026-06-18):
    # on a 32-Q English+Hinglish+Hindi benchmark dense beat hybrid (src_recall
    # 0.91 vs 0.78) — BM25 is lexical and can't cross-lingual-match Hinglish/Hindi
    # queries to the English corpus, so RRF mixing it in DILUTED the strong dense
    # results. BM25 still serves as a fallback when dense is empty (see retrieval.py).
    RETRIEVAL_MODE: str = "dense"
    RETRIEVAL_FETCH_MULTIPLIER: int = 8     # fetch top_k * this before fusion/rerank
    RRF_K: int = 60                         # reciprocal rank fusion constant
    CONTEXT_EXPANSION: bool = True          # child chunk -> fuller parent text
    # Off: BM25+RRF retrieval is strong on its own (eval: 0.92/1.00/0.81) and this
    # avoids a 2nd Gemini call per query. For production precision, prefer a local
    # cross-encoder (e.g. bge-reranker) over the LLM reranker — no API quota.
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "gemini-2.5-flash"

    # ─── Contextual Retrieval (Anthropic technique) — A/B prototype ──────────
    # When ON, dense search targets a SEPARATE zvec collection whose chunks were
    # prefixed at ingest with a 1-line LLM-generated context situating each chunk
    # in its document (reduces context-loss / retrieval misses). The base index
    # (blostem_chunks) is untouched, so flipping this flag is a clean A/B:
    #   build:  python scripts/build_zvec_contextual_index.py   (builds the ctx index)
    #   A/B:    CONTEXTUAL_RETRIEVAL=true → queries hit the ctx index; false → base.
    CONTEXTUAL_RETRIEVAL: bool = False
    ZVEC_CONTEXTUAL_COLLECTION: str = "blostem_chunks_ctx"
    # Context generation runs an LLM per chunk at INGEST only (zero query latency).
    # Default Groq (high throughput, off the Gemini 20/day wall — same as HyPE).
    CONTEXTUAL_LLM_PROVIDER: str = "groq"          # groq | gemini
    CONTEXTUAL_LLM_MODEL: str = "openai/gpt-oss-120b"
    CONTEXTUAL_DOC_BUDGET: int = 6000              # max chars of doc context per source

    class Config:
        env_file = ".env"
        extra = "ignore"  # tolerate extra .env keys (e.g. voice keys read by voice_agent)

settings = Settings()
