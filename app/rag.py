import google.generativeai as genai
from pinecone import Pinecone
from app.config import settings
from app.models import ChatResponse, SourceChunk

class RAGEngine:
    def __init__(self):
        self.pinecone_index = None
        
    def initialize(self):
        """Initialize Google AI and Pinecone client."""
        if settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            
        if settings.PINECONE_API_KEY:
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            self.pinecone_index = pc.Index(settings.PINECONE_INDEX_NAME)

    def get_embedding(self, text: str, is_query: bool = False) -> list[float]:
        """Get embeddings using Gemini Embedding 2 with task types."""
        # For Gemini Embedding 2, we use task_type
        task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
        
        # Adding task prefix explicitly as recommended in the prompt
        formatted_text = f"task: question answering | query: {text}" if is_query else text
        
        try:
            result = genai.embed_content(
                model=settings.EMBEDDING_MODEL,
                content=formatted_text,
                task_type=task_type,
                output_dimensionality=768
            )
            return result['embedding']
        except Exception as e:
            print(f"Embedding error: {e}")
            # Mock embedding for fallback during setup
            return [0.0] * 768

    def retrieve_chunks(self, query: str, top_k: int = 3) -> list[SourceChunk]:
        """Retrieve top-k relevant chunks from Pinecone with dynamic context expansion."""
        query_vector = self.get_embedding(query, is_query=True)
        
        try:
            # Stage 1: Retrieve precise child/faq chunks
            search_result = self.pinecone_index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )
            
            sources = []
            for match in search_result.matches:
                meta = match.metadata
                score = match.score
                text = meta.get("text", "No text found")
                
                # Stage 2: Dynamic Context Expansion for hierarchical chunks
                # If a child chunk has moderate confidence (< 0.75), fetch its parent chunk
                if meta.get("chunk_type") == "child" and "parent_id" in meta and score < 0.75:
                    parent_id = meta["parent_id"]
                    try:
                        parent_res = self.pinecone_index.fetch(ids=[parent_id])
                        if parent_id in parent_res.vectors:
                            # Replace the child text with the full parent context
                            parent_meta = parent_res.vectors[parent_id].metadata
                            text = parent_meta.get("text", text)
                            print(f"Expanded context for child {match.id} -> parent {parent_id}")
                    except Exception as e:
                        print(f"Error fetching parent context: {e}")

                title = meta.get("section", meta.get("question_id", "Extracted Chunk"))
                sources.append(SourceChunk(
                    title=title,
                    text=text,
                    source_url=meta.get("source", ""),
                    relevance_score=score
                ))
            return sources
        except Exception as e:
            print(f"Retrieval error: {e}")
            return []

    def process_query(self, query: str, language: str) -> ChatResponse:
        """Main RAG pipeline: Retrieve -> Prompt -> Generate."""
        # 1. Retrieve
        sources = self.retrieve_chunks(query)
        
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
