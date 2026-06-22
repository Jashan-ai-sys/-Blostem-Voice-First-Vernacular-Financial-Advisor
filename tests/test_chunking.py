"""
Wave-3 chunking/cleaning tests — offline (uses a real data PDF, no API keys).
Run:  python -m pytest tests/test_chunking.py   OR   python tests/test_chunking.py
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
settings.PDF_EXTRACTOR = "pypdf"  # deterministic + offline; don't pull Docling models in tests

from app.chunking import clean_text, chunk_pdf, _is_page_number, _slug


def test_clean_dehyphenates_across_linebreaks():
    assert "deduction" in clean_text("deduc-\ntion of tax")


def test_clean_joins_soft_linebreaks_keeps_paragraphs():
    out = clean_text("line one\nline two\n\nnew para")
    assert "line one line two" in out
    assert "\n\n" in out  # paragraph break preserved


def test_clean_collapses_whitespace_and_normalizes():
    assert clean_text("a    b\t c") == "a b c"


def test_clean_strips_docling_image_placeholders():
    assert "image" not in clean_text("Real text <!-- image --> more text").lower()


def test_is_page_number():
    assert _is_page_number("Page 1 of 4")
    assert _is_page_number("  3  ")
    assert not _is_page_number("Section 3 covers TDS")


def test_slug_namespacing():
    assert _slug("FN-121.pdf") == "fn_121"
    assert _slug("data/raw/tax_slabs_fy25_26.md") == "tax_slabs_fy25_26"


def test_chunk_pdf_produces_clean_hierarchical_chunks():
    pdf = os.path.join(os.path.dirname(__file__), "../data/FN-121.pdf")
    chunks = chunk_pdf(pdf)
    assert chunks, "no chunks produced"
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"
    types = {c["metadata"]["chunk_type"] for c in chunks}
    assert "parent" in types and "child" in types, "expected parent + child chunks"
    # cleaning removed the 'Page X of Y' footer artifact and mojibake
    joined = " ".join(c["text"] for c in chunks)
    assert "Page 1 of" not in joined
    assert "�" not in joined
    # every child links to a real parent
    parent_ids = {c["chunk_id"] for c in chunks if c["metadata"]["chunk_type"] == "parent"}
    for c in chunks:
        if c["metadata"]["chunk_type"] == "child":
            assert c["metadata"]["parent_id"] in parent_ids


def test_image_only_pdf_degrades_gracefully():
    # Scanned/image PDFs have no extractable text → empty chunk list, no crash.
    # (Production follow-up: OCR fallback for these.)
    pdf = os.path.join(os.path.dirname(__file__), "../data/depositinsurancefaq's.pdf")
    if os.path.exists(pdf):
        assert chunk_pdf(pdf) == []


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} chunking tests passed")


if __name__ == "__main__":
    _run()
