"""
Document extraction — Docling (preferred) with a pypdf fallback.
================================================================
Docling converts PDFs/scans/Office docs into clean structured Markdown:
- preserves headings, reading order, and tables (as Markdown tables)
- runs OCR on scanned/image-only PDFs that pypdf can't read at all

The extractor is selected by settings.PDF_EXTRACTOR. If Docling isn't installed
or fails on a file, we transparently fall back to pypdf so ingestion never hard-
fails. Docling is heavy and downloads layout/OCR models on first use, so it's an
opt-in dependency (see requirements.txt).
"""

from __future__ import annotations

from app.config import settings

# Cache the converter — model loading is expensive.
_DOCLING_CONVERTER = None


def docling_markdown(path: str) -> str | None:
    """Convert a document to Markdown via Docling. Returns None if unavailable."""
    global _DOCLING_CONVERTER
    try:
        if _DOCLING_CONVERTER is None:
            from docling.document_converter import DocumentConverter
            _DOCLING_CONVERTER = DocumentConverter()
        result = _DOCLING_CONVERTER.convert(path)
        return result.document.export_to_markdown()
    except ImportError:
        print("[extract] Docling not installed; falling back to pypdf. (pip install docling)")
        return None
    except Exception as e:
        print(f"[extract] Docling failed on {path}: {e}; falling back to pypdf.")
        return None


def _pypdf_text(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def extract_document(path: str) -> tuple[str, str]:
    """Extract a document's text.

    Returns (text, extractor) where extractor is "docling" or "pypdf" so the
    caller can pick the right downstream cleaning (Docling output is already
    structured Markdown; pypdf output is raw per-page text needing more cleanup).
    """
    if settings.PDF_EXTRACTOR == "docling":
        md = docling_markdown(path)
        if md is not None and md.strip():
            return md, "docling"
    return _pypdf_text(path), "pypdf"
