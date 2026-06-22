"""
Build the CONTEXTUAL-RETRIEVAL zvec index (Anthropic technique) into a SEPARATE
collection — the live base index (blostem_chunks) is never touched, so this is a
clean A/B.

Each chunk gets a 1-line LLM-generated context prepended before embedding
(app/contextual.py). Context generation uses Groq by default (off the Gemini
free-tier wall); set CONTEXTUAL_LLM_PROVIDER/MODEL to change.

Run:   python scripts/build_zvec_contextual_index.py
Then:  set CONTEXTUAL_RETRIEVAL=true in .env and restart to A/B it.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.ingestion import load_chunks
from app import contextual, zvec_store


def main():
    chunks = load_chunks()
    print(f"[ctx] contextualizing {len(chunks)} chunks via "
          f"{settings.CONTEXTUAL_LLM_PROVIDER}:{settings.CONTEXTUAL_LLM_MODEL} …")
    contextualized = contextual.contextualize_chunks(chunks)
    print(f"[ctx] embedding into '{settings.ZVEC_CONTEXTUAL_COLLECTION}' "
          f"(base index untouched) …")
    result = zvec_store.build_index(contextualized, collection=settings.ZVEC_CONTEXTUAL_COLLECTION)
    print(f"[ctx] done: {result}")
    print("[ctx] A/B: set CONTEXTUAL_RETRIEVAL=true in .env + restart to query this index.")


if __name__ == "__main__":
    main()
