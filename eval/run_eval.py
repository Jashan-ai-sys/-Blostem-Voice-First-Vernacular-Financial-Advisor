"""
Retrieval evaluation harness (Phase 19)
=======================================
Scores the retriever against a benchmark of {question, expected_source,
expected_keywords} so retrieval/extraction changes become *measurable*.

Metrics (top-k):
  - source_recall@k : did a chunk from the expected document appear in top-k?
  - keyword_recall  : did the answer's key terms appear in the top-k text?
  - MRR             : reciprocal rank of the first chunk from the expected source

Usage:
  python eval/run_eval.py                  # score current RETRIEVAL_MODE
  python eval/run_eval.py --compare        # dense vs sparse vs hybrid side-by-side
  python eval/run_eval.py --min-recall 0.7 # CI gate: exit 1 if keyword_recall below

Note: dense/hybrid need a populated Pinecone index; with none, dense scores 0 and
hybrid == sparse (BM25 carries). Reranking is disabled here to isolate retrieval.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.rag import RAGEngine

BENCH_PATH = os.path.join(os.path.dirname(__file__), "benchmark.jsonl")


def load_benchmark(path: str = BENCH_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate(engine: RAGEngine, items: list[dict], top_k: int, mode: str) -> dict:
    settings.RETRIEVAL_MODE = mode
    s_hits = k_hits = mrr = 0.0
    rows = []
    for it in items:
        chunks = engine.retrieve_chunks(it["question"], top_k=top_k)
        srcs = [(c.source_url or "").lower() for c in chunks]
        text = " ".join(c.text.lower() for c in chunks)
        exp = it["expected_source"].lower()

        src_hit = any(exp in s for s in srcs)
        kw_hit = any(kw.lower() in text for kw in it["expected_keywords"])
        rank = next((i for i, s in enumerate(srcs) if exp in s), None)
        rr = 1.0 / (rank + 1) if rank is not None else 0.0

        s_hits += src_hit
        k_hits += kw_hit
        mrr += rr
        rows.append((it["question"], src_hit, kw_hit, round(rr, 2)))

    n = len(items)
    return {
        "source_recall": s_hits / n,
        "keyword_recall": k_hits / n,
        "mrr": mrr / n,
        "rows": rows,
        "n": n,
    }


def print_report(metrics: dict, mode: str, top_k: int) -> None:
    print(f"\n=== Retrieval eval | mode={mode} | top_k={top_k} | n={metrics['n']} ===")
    print(f"{'src':>4} {'kw':>4} {'mrr':>5}  question")
    for q, sh, kh, rr in metrics["rows"]:
        print(f"{'  Y' if sh else '  .':>4} {'  Y' if kh else '  .':>4} {rr:>5.2f}  {q[:62]}")
    print("-" * 78)
    print(f"source_recall@{top_k}: {metrics['source_recall']:.2f}   "
          f"keyword_recall: {metrics['keyword_recall']:.2f}   MRR: {metrics['mrr']:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true", help="score dense vs sparse vs hybrid")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-recall", type=float, default=None, help="CI gate on keyword_recall")
    ap.add_argument("--bench", default=BENCH_PATH, help="path to a benchmark .jsonl")
    args = ap.parse_args()

    settings.RERANK_ENABLED = False  # isolate retrieval quality from the reranker
    engine = RAGEngine()
    engine.initialize()
    items = load_benchmark(args.bench)

    if args.compare:
        print(f"\n=== Mode comparison | top_k={args.top_k} | n={len(items)} ===")
        print(f"{'mode':>8} | source_recall | keyword_recall |  MRR")
        for mode in ("dense", "sparse", "hybrid"):
            m = evaluate(engine, items, args.top_k, mode)
            print(f"{mode:>8} |     {m['source_recall']:.2f}      |      {m['keyword_recall']:.2f}      | {m['mrr']:.2f}")
        return

    m = evaluate(engine, items, args.top_k, settings.RETRIEVAL_MODE or "hybrid")
    print_report(m, settings.RETRIEVAL_MODE or "hybrid", args.top_k)
    if args.min_recall is not None and m["keyword_recall"] < args.min_recall:
        print(f"\nFAIL: keyword_recall {m['keyword_recall']:.2f} < gate {args.min_recall}")
        sys.exit(1)


if __name__ == "__main__":
    main()
