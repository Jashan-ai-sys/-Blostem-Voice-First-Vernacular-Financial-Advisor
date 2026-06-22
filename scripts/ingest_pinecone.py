"""
Pinecone ingestion CLI — thin wrapper over app.ingestion.

The real logic (change detection, idempotent upsert, stale deletion, manifest)
lives in app/ingestion.py so it's importable and testable. Keys come from .env.

Usage:
    python scripts/ingest_pinecone.py            # embed new/changed, sync index
    python scripts/ingest_pinecone.py --dry-run  # show the plan, touch nothing
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion import run_ingest

if __name__ == "__main__":
    run_ingest(dry_run="--dry-run" in sys.argv)
