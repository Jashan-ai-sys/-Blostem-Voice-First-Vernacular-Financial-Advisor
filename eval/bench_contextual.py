"""
Small-sample A/B: Contextual Retrieval vs the current (raw) chunking.

Fair test: build TWO temporary zvec collections from the SAME subset of chunks —
one raw ("bench_base"), one contextualized ("bench_ctx") — so the only difference
is the Anthropic-style context prefix. Then score both on eval/benchmark.jsonl.

Subset = a few chunks per benchmark source (default 12), to keep Groq calls low.
This is a DIRECTIONAL sanity benchmark (small index, 12 Qs), not production-grade:
the absolute recall is inflated (few distractors), but the base→ctx DELTA is the
honest signal for contextualization.

Run:  python eval/bench_contextual.py --per-source 12 --top-k 5
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows console/redirect defaults to cp1252 → Devanagari/→ in contexts crash on
# print. Force UTF-8 so sample context lines and arrows render safely.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.config import settings
from app.ingestion import load_chunks
from app import contextual, zvec_store
from app.rag import RAGEngine
from eval.run_eval import load_benchmark, evaluate

BASE_COLL, CTX_COLL = "bench_base", "bench_ctx"


def pick_subset(chunks, items, per_source):
    srcs = {it["expected_source"].lower() for it in items}
    seen = {}
    sub = []
    for c in chunks:
        s = (c.get("metadata", {}).get("source") or "").lower()
        if not any(es in s or s in es for es in srcs):
            continue
        if seen.get(s, 0) >= per_source:
            continue
        seen[s] = seen.get(s, 0) + 1
        sub.append(c)
    return sub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=12)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    chunks = load_chunks()
    items = load_benchmark()
    sub = pick_subset(chunks, items, args.per_source)
    print(f"[bench] subset = {len(sub)} chunks (~{len(sub)} Groq calls), {len(items)} questions\n")

    # 1) raw subset index
    print("[bench] building RAW subset index…")
    zvec_store.build_index(sub, collection=BASE_COLL)

    # 2) contextualized subset index (same chunks)
    print(f"[bench] contextualizing via {settings.CONTEXTUAL_LLM_PROVIDER}:{settings.CONTEXTUAL_LLM_MODEL}…")
    ctx = contextual.contextualize_chunks(sub)
    print("[bench] building CONTEXTUAL subset index…")
    zvec_store.build_index(ctx, collection=CTX_COLL)

    # show a few sample context lines so we can eyeball quality
    print("\n[bench] sample context prefixes:")
    for c in ctx[:3]:
        if c.get("metadata", {}).get("contextualized"):
            prefix = c["text"].split("\n\n", 1)[0]
            print(f"   • [{c['chunk_id']}] {prefix[:110]}")

    # 3) eval both — flip the active collection via the ctx slot, dense mode
    settings.RERANK_ENABLED = False
    settings.CONTEXTUAL_RETRIEVAL = True   # routes zvec to ZVEC_CONTEXTUAL_COLLECTION
    engine = RAGEngine()
    engine.initialize()

    results = {}
    for label, coll in [("base (raw)", BASE_COLL), ("contextual", CTX_COLL)]:
        settings.ZVEC_CONTEXTUAL_COLLECTION = coll
        results[label] = evaluate(engine, items, args.top_k, mode="dense")

    print(f"\n=== Contextual Retrieval A/B | subset={len(sub)} | top_k={args.top_k} | n={len(items)} ===")
    print(f"{'variant':>12} | source_recall | keyword_recall |  MRR")
    for label in ("base (raw)", "contextual"):
        m = results[label]
        print(f"{label:>12} |     {m['source_recall']:.2f}      |      {m['keyword_recall']:.2f}      | {m['mrr']:.2f}")
    b, c = results["base (raw)"], results["contextual"]
    print(f"\nDELTA (ctx - base): source_recall {c['source_recall']-b['source_recall']:+.2f}  "
          f"keyword_recall {c['keyword_recall']-b['keyword_recall']:+.2f}  MRR {c['mrr']-b['mrr']:+.2f}")
    print("\nNote: small-sample, low-distractor index -> absolute numbers inflated; trust the DELTA.")


if __name__ == "__main__":
    main()
