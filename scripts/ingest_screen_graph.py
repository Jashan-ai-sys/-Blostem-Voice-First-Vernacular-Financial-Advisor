"""
Targeted ingest: embed ONLY the screen-graph chunks (doc_type=screen_graph) into
Pinecone. The full-corpus ingest blows the free-tier embedding quota; this needs
only ~43 embeds, so it succeeds on free tier (once the daily quota has reset) and
gets the Figma screens/concepts/error screens into DENSE retrieval.

Run:  .venv/Scripts/python.exe scripts/ingest_screen_graph.py
"""
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ingestion import load_chunks, load_manifest, save_manifest, _open_index, _embed, _flatten_metadata, content_hash

DOC_TYPE = "screen_graph"
PACE_SECONDS = 1.2  # stay under the free-tier per-minute embedding cap (~100/min)


def main():
    chunks = [c for c in load_chunks() if c.get("metadata", {}).get("doc_type") == DOC_TYPE]
    print(f"[screen-graph ingest] {len(chunks)} chunks to embed")
    if not chunks:
        print("nothing to do"); return

    index = _open_index()
    manifest = load_manifest()
    vectors, failed = [], []
    for c in chunks:
        cid, text = c["chunk_id"], c.get("text", "")
        try:
            vectors.append({"id": cid, "values": _embed(text), "metadata": _flatten_metadata(c)})
            manifest[cid] = {"hash": content_hash(text), "source": c.get("metadata", {}).get("source", ""), "version": ""}
        except Exception as e:
            failed.append(cid)
            print(f"  embed failed {cid}: {str(e)[:80]}")
        time.sleep(PACE_SECONDS)  # pace under the per-minute quota

    if vectors:
        index.upsert(vectors=vectors)
    save_manifest(manifest)
    print(f"[screen-graph ingest] embedded {len(vectors)}, failed {len(failed)}")
    if failed:
        print("  -> quota likely still exhausted; retry after reset or enable billing.")


if __name__ == "__main__":
    main()
