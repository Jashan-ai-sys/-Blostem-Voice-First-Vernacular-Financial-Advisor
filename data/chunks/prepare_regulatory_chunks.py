"""
Prepare structured JSONL chunks from raw regulatory markdown files.
Uses hierarchical parent+child chunking matching existing retrieval_chunks.jsonl format.
"""
import json
import re
import os

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "regulatory_chunks.jsonl")
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw")

# ── Document definitions ──────────────────────────────────────────────
DOCS = [
    {
        "file": "DPDPA_data_handling.md",
        "source": "DPDPA_data_handling.md",
        "doc_type": "regulation",
        "topic": ["dpdpa", "data_privacy", "pii", "consent", "fintech_compliance"],
    },
    {
        "file": "KYC_VKYC_norms.md",
        "source": "KYC_VKYC_norms.md",
        "doc_type": "regulation",
        "topic": ["kyc", "vkyc", "ckyc", "ekyc", "pmla", "onboarding"],
    },
    {
        "file": "RBI_FD_DICGC_summary.md",
        "source": "RBI_FD_DICGC_summary.md",
        "doc_type": "regulation",
        "topic": ["rbi", "fd", "dicgc", "deposit_insurance", "tds", "premature_withdrawal"],
    },
    {
        "file": "SEBI_MF_AIF_SIF_summary.md",
        "source": "SEBI_MF_AIF_SIF_summary.md",
        "doc_type": "regulation",
        "topic": ["sebi", "mutual_funds", "sip", "aif", "sif", "pms", "taxation"],
    },
]


def split_into_sections(text: str):
    """Split markdown by ## headings into (heading, body) pairs."""
    pattern = r"^(## .+)$"
    parts = re.split(pattern, text, flags=re.MULTILINE)

    sections = []
    # parts[0] = preamble before first ##
    i = 1
    while i < len(parts):
        heading = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if body:
            sections.append((heading, body))
        i += 2
    return sections


def chunk_body(body: str, max_chars: int = 800):
    """Split body into child-sized pieces on paragraph boundaries."""
    paragraphs = re.split(r"\n{2,}", body)
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current.strip())
            current = para
        else:
            current = current + "\n\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def process_document(doc_cfg: dict, doc_index: int):
    """Process one markdown file into parent + child chunks."""
    filepath = os.path.join(RAW_DIR, doc_cfg["file"])
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    # Strip builder-pack boilerplate lines & trailing update line
    lines = raw.split("\n")
    clean_lines = []
    for line in lines:
        if line.startswith("**Builder-Pack"):
            continue
        if line.startswith("*Last updated:"):
            continue
        clean_lines.append(line)
    text = "\n".join(clean_lines)

    sections = split_into_sections(text)
    all_chunks = []
    prefix = f"reg{doc_index}"

    for sec_idx, (heading, body) in enumerate(sections):
        # Skip citation-only sections
        if "citation" in heading.lower() and len(body) < 300:
            continue

        parent_id = f"{prefix}_sec_{sec_idx}"
        full_text = f"{heading}\n{body}"

        # Parent chunk: full section
        parent = {
            "chunk_id": parent_id,
            "text": full_text,
            "metadata": {
                "source": doc_cfg["source"],
                "section": heading,
                "chunk_type": "parent",
                "doc_type": doc_cfg["doc_type"],
                "topic": doc_cfg["topic"],
            },
        }
        all_chunks.append(parent)

        # Child chunks: smaller pieces with section context prefix
        children = chunk_body(body, max_chars=800)
        for child_idx, child_text in enumerate(children):
            child = {
                "chunk_id": f"{parent_id}_child_{child_idx:03d}",
                "text": f"{heading} - Context: {child_text}",
                "metadata": {
                    "source": doc_cfg["source"],
                    "section": heading,
                    "parent_id": parent_id,
                    "chunk_type": "child",
                    "doc_type": doc_cfg["doc_type"],
                    "topic": doc_cfg["topic"],
                },
            }
            all_chunks.append(child)

    return all_chunks


def main():
    all_chunks = []
    for idx, doc in enumerate(DOCS):
        chunks = process_document(doc, idx)
        all_chunks.extend(chunks)
        print(f"  [OK] {doc['file']}: {len(chunks)} chunks ({len([c for c in chunks if c['metadata']['chunk_type']=='parent'])} parents)")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"\n[DONE] Written {len(all_chunks)} chunks -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
