"""Tests for the OKF (Open Knowledge Format) loader/consumer (app/okf.py).

Self-contained: builds a tiny OKF bundle in a temp dir, so it doesn't depend on
data/okf existing or on any network/model. Covers parse, bundle loading (index
exclusion), chunk conversion shape, and the no-frontmatter edge case.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import okf

SCREEN_MD = """---
type: Screen
title: PAN Verification
description: Where the user enters their PAN.
tags: [screen, kyc]
timestamp: '2026-06-21T00:00:00Z'
---

## What the user does

Enter PAN. See [Tenure](../concepts/tenure.md).
"""

CONCEPT_MD = """---
type: Concept
title: Tenure
description: How long the money is locked in.
tags: [concept, duration]
---

The length of time your money stays locked in the FD.
"""

INDEX_MD = """---
type: Index
title: Screens
---

- [PAN Verification](pan_verification.md)
"""


def _bundle() -> str:
    d = tempfile.mkdtemp(prefix="okf_test_")
    os.makedirs(os.path.join(d, "screens"))
    os.makedirs(os.path.join(d, "concepts"))
    with open(os.path.join(d, "screens", "pan_verification.md"), "w", encoding="utf-8") as f:
        f.write(SCREEN_MD)
    with open(os.path.join(d, "concepts", "tenure.md"), "w", encoding="utf-8") as f:
        f.write(CONCEPT_MD)
    with open(os.path.join(d, "screens", "index.md"), "w", encoding="utf-8") as f:
        f.write(INDEX_MD)
    return d


def test_parse_doc_frontmatter_and_body():
    d = _bundle()
    doc = okf.parse_doc(os.path.join(d, "screens", "pan_verification.md"))
    assert doc["frontmatter"]["type"] == "Screen"
    assert doc["frontmatter"]["title"] == "PAN Verification"
    assert doc["frontmatter"]["tags"] == ["screen", "kyc"]
    assert "What the user does" in doc["body"]
    assert "Tenure" in doc["body"]  # cross-link preserved in body


def test_load_bundle_excludes_index():
    d = _bundle()
    docs = okf.load_bundle(d)
    names = [os.path.basename(x["path"]) for x in docs]
    assert "index.md" not in names          # reserved nav file excluded
    assert len(docs) == 2                    # screen + concept only


def test_okf_to_chunks_shape():
    d = _bundle()
    chunks = okf.okf_to_chunks(d)
    assert len(chunks) == 2
    pan = next(c for c in chunks if c["chunk_id"].endswith("pan_verification"))
    assert pan["chunk_id"] == "okf__screens__pan_verification"
    # source is path-specific so retrieval results are attributable to the concept
    assert pan["metadata"]["source"] == "okf:screens/pan_verification.md"
    assert pan["metadata"]["okf_type"] == "Screen"
    assert pan["metadata"]["okf_path"] == "screens/pan_verification.md"
    # text leads with the self-describing title + description (the situating context)
    assert pan["text"].startswith("PAN Verification. Where the user enters their PAN.")


def test_no_frontmatter_tolerated():
    d = tempfile.mkdtemp(prefix="okf_test_")
    with open(os.path.join(d, "plain.md"), "w", encoding="utf-8") as f:
        f.write("just a body, no frontmatter here")
    docs = okf.load_bundle(d)
    assert docs[0]["frontmatter"] == {}
    assert "just a body" in docs[0]["body"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
