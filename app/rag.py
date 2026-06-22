import google.generativeai as genai
from pinecone import Pinecone
from app.config import settings
from app.models import ChatResponse, SourceChunk
from app.retrieval import HybridRetriever

class RAGEngine:
    def __init__(self):
        self.pinecone_index = None
        self._retriever = None

    def initialize(self):
        """Initialize Google AI and Pinecone client."""
        if settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)

        if settings.PINECONE_API_KEY:
            try:
                pc = Pinecone(api_key=settings.PINECONE_API_KEY)
                self.pinecone_index = pc.Index(settings.PINECONE_INDEX_NAME)
            except Exception as e:
                # Index not created yet / unreachable → fall back to BM25-only retrieval.
                print(f"Pinecone index unavailable ({e}); using BM25-only retrieval.")
                self.pinecone_index = None

        # Hybrid retriever: dense search is this engine's Pinecone query;
        # sparse (BM25) + fusion + rerank live in the retrieval module.
        self._retriever = HybridRetriever(dense_search=self._dense_search)

    def get_embedding(self, text: str, is_query: bool = False) -> list[float]:
        """Embed a query/document. Backend is settings.EMBEDDING_BACKEND:
        "local" (default) = multilingual-e5-base in-process; "gemini" = legacy API.

        Queries are PII-masked (PAN/Aadhaar/phone) regardless of backend. On
        failure this RAISES rather than returning a fake zero vector — the caller
        (_dense_search) catches it and drops to BM25-only, so an embedding outage
        degrades retrieval instead of silently poisoning it (voice stays live)."""
        if is_query:
            from app.pii_masker import mask_pii
            safe = mask_pii(text)
        else:
            safe = text

        if settings.EMBEDDING_BACKEND == "local":
            try:
                from app.embedder import embed_one
                return embed_one(safe, is_query=is_query)
            except Exception as e:
                print(f"[rag] local embedding failed ({e}); falling back to BM25-only.")
                raise

        # Legacy Gemini path (BACKEND=gemini).
        task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
        formatted_text = f"task: question answering | query: {safe}" if is_query else safe
        try:
            result = genai.embed_content(
                model=settings.EMBEDDING_MODEL,
                content=formatted_text,
                task_type=task_type,
                output_dimensionality=settings.EMBEDDING_DIM,
            )
            return result['embedding']
        except Exception as e:
            print(f"[rag] embedding failed ({e}); falling back to BM25-only for this query.")
            raise

    def _dense_search(self, query: str, top_k: int, as_of: int | None = None) -> list[dict]:
        """Dense vector search → normalized hit dicts for the hybrid retriever.
        Backend is config-selected: 'zvec' (local in-memory, no quota — default)
        or 'pinecone'. Empty list on any failure → caller falls back to BM25.

        as_of (epoch int): query the HISTORICAL index (Pinecone only)."""
        # zvec: local embeddings + in-process vector DB; no quota, no network.
        if getattr(settings, "VECTOR_BACKEND", "zvec") == "zvec" and as_of is None:
            try:
                from app import zvec_store, retrieval_scope
                sc = retrieval_scope.current()
                return zvec_store.query(query, top_k=top_k,
                                        tenant=sc.get("tenant"), filters=sc.get("filters"))
            except Exception as e:
                print(f"[rag] zvec search error: {e}; falling back to BM25-only.")
                return []

        if self.pinecone_index is None:
            return []
        try:
            query_vector = self.get_embedding(query, is_query=True)
            kwargs = {"vector": query_vector, "top_k": top_k, "include_metadata": True}
            if as_of is not None:
                # Historical index: version active at `as_of` (valid_from ≤ t < valid_to).
                kwargs["filter"] = {"valid_from": {"$lte": as_of}, "valid_to": {"$gt": as_of}}
            elif settings.VERSIONED_INDEX:
                # Active index: only current versions (Phase 7).
                kwargs["filter"] = {"is_active": True}
            result = self.pinecone_index.query(**kwargs)
            hits = []
            for match in result.matches:
                meta = match.metadata or {}
                # Fuse on the plain chunk_id (vector ids may be version-suffixed).
                hits.append({
                    "id": meta.get("chunk_id", match.id),
                    "score": match.score,
                    "text": meta.get("text", ""),
                    "metadata": meta,
                })
            return hits
        except Exception as e:
            print(f"Dense search error: {e}")
            return []

    def retrieve_chunks(self, query: str, top_k: int = 3, as_of: int | None = None) -> list[SourceChunk]:
        """Hybrid retrieve: dense + BM25 fused, reranked, parent-expanded.
        With `as_of` (epoch int): historical, dense-only (see HybridRetriever)."""
        if self._retriever is None:
            self._retriever = HybridRetriever(dense_search=self._dense_search)
        return self._retriever.retrieve(query, top_k=top_k, as_of=as_of)

    def process_query(self, query: str, language: str, as_of: int | None = None) -> ChatResponse:
        """Main RAG pipeline: Retrieve -> Prompt -> Generate."""
        # 1. Retrieve (historical if as_of given)
        sources = self.retrieve_chunks(query, as_of=as_of)
        
        # 2. Format Context
        context_text = "\n\n".join([f"Source: {s.title}\n{s.text}" for s in sources])
        
        # 3. Construct Prompt
        prompt = f"""
You are a conservative, knowledgeable financial advisor for India.
You must answer the user's question ONLY using the provided context.
If the context does not contain the answer, say "I'm not sure" and refuse to guess.
Mention when rules may vary by bank or date.
Prefer "please verify latest official source" for changing tax rules.
Refuse investment advice beyond factual product explanation.

Format your response:
1. Short answer in the requested language.
2. 2-4 bullet explanation points.
3. Verification note when policy/date sensitivity exists.

Context:
{context_text}

Question: {query}
Requested Language: {language}
"""
        
        # 4. Generate Answer
        try:
            model = genai.GenerativeModel(settings.GENERATION_MODEL)
            response = model.generate_content(prompt)
            answer_text = response.text
        except Exception as e:
            print(f"Generation error: {e}")
            answer_text = "I am currently unable to generate an answer due to an API error."

        return ChatResponse(
            answer=answer_text,
            sources=sources
        )
