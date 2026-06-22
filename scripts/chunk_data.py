"""
Batch chunker — regenerates data/chunks/retrieval_chunks.jsonl from source docs.

Chunking logic lives in app/chunking.py (shared with the /ingest/upload endpoint)
so the batch corpus and self-serve uploads are produced identically.

Usage:  python scripts/chunk_data.py
"""

import glob
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.chunking import chunk_markdown, chunk_pdf


def main():
    raw_dir = os.path.join(os.path.dirname(__file__), "../data/raw")
    data_dir = os.path.join(os.path.dirname(__file__), "../data")
    output_path = os.path.join(os.path.dirname(__file__), "../data/chunks/retrieval_chunks.jsonl")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_chunks = []

    for filepath in glob.glob(os.path.join(raw_dir, "*.md")):
        filename = os.path.basename(filepath)
        print(f"Processing {filename}...")
        with open(filepath, "r", encoding="utf-8") as f:
            all_chunks.extend(chunk_markdown(f.read(), filename))

    for filepath in glob.glob(os.path.join(data_dir, "*.pdf")):
        filename = os.path.basename(filepath)
        print(f"Processing PDF {filename}...")
        all_chunks.extend(chunk_pdf(filepath, source=filename))

    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk) + "\n")
    print(f"Wrote {len(all_chunks)} chunks to {output_path}")


if __name__ == "__main__":
    main()
