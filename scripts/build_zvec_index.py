"""
Build the zvec in-memory dense index from the corpus, using LOCAL embeddings.
No Pinecone, no Google quota — runs fully on-device, so the whole corpus
(incl. screen-graph + error chunks) is embedded instantly and repeatably.

Run:  .venv/Scripts/python.exe scripts/build_zvec_index.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion import load_index_corpus
from app import zvec_store


def main():
    # Source of truth = docs corpus + OKF bundle (screens/concepts/errors),
    # with the legacy screen_graph chunks dropped (superseded by OKF).
    chunks = load_index_corpus()
    print(f"[zvec] embedding {len(chunks)} chunks with {zvec_store.EMBED_MODEL} (local, no quota)…")
    result = zvec_store.build_index(chunks)
    print(f"[zvec] done: {result}")


if __name__ == "__main__":
    main()
