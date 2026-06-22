"""
Chunking & cleaning — production-grade static document ingestion
===============================================================
Single source of truth for turning a raw document into retrieval chunks, used
by both the batch script (scripts/chunk_data.py) and the self-serve upload
endpoint (POST /ingest/upload).

PDF path:  extract → strip repeating headers/footers + page numbers → clean
           (de-hyphenate, join soft line breaks, normalize unicode/whitespace)
           → hierarchical parent/child chunks with source-namespaced ids.

Namespacing every chunk_id by source file prevents the cross-file id collisions
that previously dropped ~66% of the corpus.
"""

from __future__ import annotations

import os
import re
import unicodedata

from langchain_text_splitters import RecursiveCharacterTextSplitter

_SEPARATORS = ["\n\n", "\n", ". ", "। ", "? ", "! ", "; ", ", ", " ", ""]


def _slug(source: str) -> str:
    """'FN-121.pdf' -> 'fn_121'. Used as the chunk_id namespace."""
    stem = os.path.splitext(os.path.basename(source))[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "doc"


# ─── Cleaning ────────────────────────────────────────────────────────────────

def _norm_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().lower()


def _is_page_number(line: str) -> bool:
    return bool(re.match(r"^\s*(page\s+)?\d+(\s*(/|of)\s*\d+)?\s*$", line, re.I))


def _detect_boilerplate(pages: list[str]) -> set[str]:
    """Lines repeating across many pages are headers/footers — drop them."""
    if len(pages) < 3:
        return set()
    counts: dict[str, int] = {}
    for raw in pages:
        for line in set(_norm_line(l) for l in raw.split("\n")):
            if 0 < len(line) < 80:
                counts[line] = counts.get(line, 0) + 1
    threshold = max(3, int(len(pages) * 0.5))
    return {line for line, n in counts.items() if n >= threshold}


def clean_text(text: str) -> str:
    """Normalize unicode, de-hyphenate, rejoin soft line breaks, collapse space."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("�", " ")  # drop mojibake/replacement chars from bad PDF decodes
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)  # strip Docling image placeholders
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)        # word split across lines
    text = re.sub(r"\n{2,}", "␞", text)            # protect paragraph breaks
    text = text.replace("\n", " ")                       # join soft line breaks
    text = text.replace("␞", "\n\n")
    text = re.sub(r"[^\S\n]+", " ", text)               # collapse intra-line space
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ─── Hierarchical chunking ───────────────────────────────────────────────────

_HEADERS_TO_SPLIT = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def _split_sections(doc_text: str) -> list[tuple[str, str]]:
    """Split markdown on headers → [(section_text, section_title)]. A coherent
    section/clause stays whole instead of being cut mid-clause by character count.
    Headerless text (e.g. the pypdf path) degrades to one section == the whole doc,
    so behaviour is unchanged for documents without markdown structure."""
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    try:
        secs = MarkdownHeaderTextSplitter(
            headers_to_split_on=_HEADERS_TO_SPLIT, strip_headers=False
        ).split_text(doc_text)
        out = [(s.page_content, " > ".join(v for v in s.metadata.values() if v)) for s in secs]
        out = [(t, sec) for t, sec in out if (t or "").strip()]
        if out:
            return out
    except Exception:
        pass
    return [(doc_text, "")]


def _hierarchical_chunks(doc_text: str, source: str, doc_type: str) -> list[dict]:
    """Section-aware hierarchical chunks: split on markdown headers FIRST so each
    parent is a coherent section/clause, then parent→child within each section.
    The section title is carried into metadata so a retrieved clause shows where it
    came from (and surfaces as the result title)."""
    prefix = _slug(source)
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1600, chunk_overlap=0, separators=_SEPARATORS
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=700, chunk_overlap=100, separators=_SEPARATORS
    )

    chunks: list[dict] = []
    pi = 0
    for sec_text, section in _split_sections(doc_text):
        sec_text = sec_text.strip()
        if not sec_text:
            continue
        for parent_text in parent_splitter.split_text(sec_text):
            parent_text = parent_text.strip()
            if not parent_text:
                continue
            pid = f"{prefix}__p{pi:03d}"
            pi += 1
            pmeta = {"source": source, "chunk_type": "parent", "doc_type": doc_type}
            if section:
                pmeta["section"] = section
            chunks.append({"chunk_id": pid, "text": parent_text, "metadata": pmeta})
            for ci, child in enumerate(child_splitter.split_text(parent_text)):
                child = child.strip()
                if not child:
                    continue
                cmeta = {"source": source, "parent_id": pid,
                         "chunk_type": "child", "doc_type": doc_type}
                if section:
                    cmeta["section"] = section
                chunks.append({"chunk_id": f"{pid}_c{ci:03d}", "text": child, "metadata": cmeta})
    return chunks


def chunk_pdf(pdf_path: str, source: str | None = None, doc_type: str = "bank_rules") -> list[dict]:
    """Extract, clean, and hierarchically chunk a PDF into retrieval chunks.

    Prefers Docling (structured Markdown + OCR for scans); falls back to the
    pypdf per-page path if Docling is unavailable or yields nothing.
    """
    from app.config import settings

    source = source or os.path.basename(pdf_path)

    if settings.PDF_EXTRACTOR == "docling":
        from app.extraction import docling_markdown
        md = docling_markdown(pdf_path)
        if md and md.strip():
            # Docling output is already clean, structured Markdown.
            return _hierarchical_chunks(clean_text(md), source, doc_type)

    return _chunk_pdf_pypdf(pdf_path, source, doc_type)


def _chunk_pdf_pypdf(pdf_path: str, source: str, doc_type: str) -> list[dict]:
    """pypdf fallback: per-page extract → strip boilerplate → clean → chunk."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = [(page.extract_text() or "") for page in reader.pages]

    boiler = _detect_boilerplate(pages)
    cleaned_pages = []
    for raw in pages:
        kept = [l for l in raw.split("\n") if _norm_line(l) not in boiler and not _is_page_number(l)]
        cleaned = clean_text("\n".join(kept))
        if cleaned.strip():
            cleaned_pages.append(cleaned)

    doc_text = "\n\n".join(cleaned_pages)
    return _hierarchical_chunks(doc_text, source, doc_type)


# ─── Markdown chunking (used by the batch script for data/raw/*.md) ───────────

def chunk_faq(text: str, source: str) -> list[dict]:
    prefix = _slug(source)
    qa_pairs = re.split(r"(?i)(?:Q\d+\.?|Question\s*\d*:|Q:)", text)
    chunks = []
    for i, qa in enumerate(qa_pairs[1:], 1):
        if not qa.strip():
            continue
        chunks.append({
            "chunk_id": f"{prefix}__faq_{i:03d}",
            "text": f"Q{i}. {qa.strip()}",
            "metadata": {"source": source, "question_id": f"Q{i}", "doc_type": "faq"},
        })
    return chunks


def chunk_markdown(text: str, source: str) -> list[dict]:
    """FAQ docs get Q&A chunking; everything else gets hierarchical chunking."""
    if "faq" in source.lower():
        chunks = chunk_faq(text, source)
        if chunks:
            return chunks
    return _hierarchical_chunks(clean_text(text), source, doc_type="guidance")
