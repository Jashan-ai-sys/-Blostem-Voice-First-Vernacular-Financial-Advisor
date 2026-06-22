"""
Wave-2 retrieval tests — fully offline (BM25 + RRF over the local corpus).
Run:  python -m pytest tests/test_retrieval.py   OR   python tests/test_retrieval.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.retrieval import reciprocal_rank_fusion, BM25Index, HybridRetriever


# ─── Reciprocal Rank Fusion ──────────────────────────────────────────────────

def test_rrf_rewards_agreement_across_rankers():
    # "b" appears in BOTH lists; "a"/"c" each in only one → agreement wins.
    dense = ["a", "b"]
    sparse = ["c", "b"]
    fused = [cid for cid, _ in reciprocal_rank_fusion([dense, sparse])]
    assert fused[0] == "b", f"expected 'b' to win fusion, got {fused}"


def test_rrf_single_ranking_preserves_order():
    fused = [cid for cid, _ in reciprocal_rank_fusion([["x", "y", "z"]])]
    assert fused == ["x", "y", "z"]


def test_rrf_unions_ids():
    fused = [cid for cid, _ in reciprocal_rank_fusion([["a"], ["b"], ["c"]])]
    assert set(fused) == {"a", "b", "c"}


# ─── BM25 over the real corpus ───────────────────────────────────────────────

def test_bm25_loads_corpus():
    idx = BM25Index()
    assert len(idx.ids) > 100, "corpus should load hundreds of chunks"
    assert all(cid in idx.store for cid in idx.ids)


def test_bm25_finds_exact_tokens():
    # Lexical query BM25 should nail (dense often fuzzes acronyms/form numbers).
    idx = BM25Index()
    hits = idx.search("Form 39 relief salary arrears", top_k=5)
    assert hits, "BM25 returned nothing for a corpus term"
    joined = " ".join(idx.store[h]["text"] for h in hits)
    assert "Form" in joined and "39" in joined


# ─── Hybrid pipeline wiring (dense stubbed; exercises fusion + expansion) ─────

def test_hybrid_falls_back_to_sparse_when_dense_empty():
    # Simulate Pinecone down/no-key: dense returns nothing, BM25 still answers.
    retriever = HybridRetriever(dense_search=lambda q, k: [])
    results = retriever.retrieve("TDS threshold on fixed deposit interest", top_k=3)
    assert results, "hybrid should still return BM25 results when dense is empty"
    assert all(r.text for r in results)


def test_hybrid_fuses_dense_and_sparse():
    idx = BM25Index()
    some_id = idx.ids[0]
    # Dense returns one real chunk; ensure it survives fusion into the output.
    dense = lambda q, k: [{"id": some_id, "score": 0.9,
                           "text": idx.store[some_id]["text"],
                           "metadata": idx.store[some_id]["metadata"]}]
    retriever = HybridRetriever(dense_search=dense)
    results = retriever.retrieve("income tax act 2025", top_k=5)
    assert results


def test_historical_as_of_is_dense_only_and_forwards_timestamp():
    # as_of must NOT touch BM25 (current corpus only) and must pass the timestamp
    # through to dense search so Pinecone can range-filter the version window.
    seen = {}
    def dense(q, k, as_of=None):
        seen["as_of"] = as_of
        return [{"id": "x__p0", "score": 0.9, "text": "old policy text",
                 "metadata": {"chunk_id": "x__p0", "source": "policy.md", "section": "S"}}]
    retriever = HybridRetriever(dense_search=dense)
    results = retriever.retrieve("refund policy", top_k=3, as_of=1735689600)
    assert seen["as_of"] == 1735689600
    assert results and results[0].text == "old policy text"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} retrieval tests passed")


if __name__ == "__main__":
    _run()
