"""
Open Knowledge Format (OKF) loader/consumer.

OKF (Google Cloud, v0.1) = a directory of markdown files, each a "concept" with
YAML frontmatter (type, title, description, resource, tags, timestamp) + a
markdown body, cross-linked with markdown links. Reserved nav files (index.md,
log.md) are not concepts.

This module is the CONSUMER end: it parses any conformant OKF bundle and turns it
into the project's retrieval-chunk shape, so OKF content flows through the same
ingestion → zvec/BM25 → RAG path as everything else. The PRODUCER (screen graph →
OKF) lives in scripts/build_okf_from_screen_graph.py.

Why this matters here: a curated OKF concept is self-describing (title +
description per doc), which is the "situating context" Contextual Retrieval injects
— so OKF content tends to retrieve well by construction. And because OKF is a
portable format, each tenant of the embeddable widget can ship their OWN bundle
(their screens/flows/concepts) and the agent consumes it with no bespoke build.
"""
from __future__ import annotations

import glob
import os

import yaml

RESERVED = {"index.md", "log.md"}   # navigation/history files, not concepts


def parse_doc(path: str) -> dict:
    """Parse one OKF markdown file → {frontmatter, body, path}. Tolerates a missing
    frontmatter block (treats the whole file as body)."""
    raw = open(path, "r", encoding="utf-8").read()
    frontmatter: dict = {}
    body = raw
    if raw.lstrip().startswith("---"):
        parts = raw.split("---", 2)          # ['', <yaml>, <body>]
        if len(parts) == 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = parts[2]
    return {"frontmatter": frontmatter, "body": body.strip(), "path": path}


def load_bundle(root: str) -> list[dict]:
    """Walk an OKF bundle directory → list of concept docs (excludes index/log)."""
    docs = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True)):
        if os.path.basename(path).lower() in RESERVED:
            continue
        docs.append(parse_doc(path))
    return docs


def _concept_id(root: str, path: str) -> str:
    rel = os.path.relpath(path, root).replace("\\", "/")
    if rel.lower().endswith(".md"):
        rel = rel[:-3]
    return "okf__" + rel.replace("/", "__")


def okf_to_chunks(root: str) -> list[dict]:
    """Turn an OKF bundle into retrieval chunks (the project chunk shape):
    {chunk_id, text, metadata}. chunk_id is derived from the file path (its OKF
    identity); text leads with title + description (the self-describing context)
    then the body; frontmatter is carried into metadata."""
    chunks = []
    for d in load_bundle(root):
        fm = d.get("frontmatter") or {}
        title = str(fm.get("title") or "")
        desc = str(fm.get("description") or "")
        head = ". ".join(p for p in (title, desc) if p)
        text = f"{head}\n\n{d['body']}".strip() if head else d["body"]
        if not text:
            continue
        rel = os.path.relpath(d["path"], root).replace("\\", "/")
        chunks.append({
            "chunk_id": _concept_id(root, d["path"]),
            "text": text,
            # source is path-specific (e.g. "okf:concepts/premature_withdrawal.md")
            # so retrieval results are attributable to the exact concept.
            "source_url": f"okf:{rel}",
            "metadata": {
                "source": f"okf:{rel}",
                "okf_type": fm.get("type"),
                "okf_path": rel,
                "title": title,
                "tags": fm.get("tags", []),
                "resource": fm.get("resource"),
                "chunk_type": "okf",
            },
        })
    return chunks
