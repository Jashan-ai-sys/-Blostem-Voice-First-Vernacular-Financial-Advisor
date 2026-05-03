import json
import re
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. FAQ chunking (Q&A pairs)
def chunk_faq(text: str, source_meta: dict) -> list[dict]:
    # Regex to split by Q1., Q2., or Q: patterns
    qa_pairs = re.split(r'(?i)(?:Q\d+\.?|Question\s*\d*:|Q:)', text)
    chunks = []
    
    for i, qa in enumerate(qa_pairs[1:], 1):  # Skip first empty split
        if not qa.strip(): continue
        chunks.append({
            "chunk_id": f"faq_{i:03d}",
            "text": f"Q{i}. {qa.strip()}",
            "metadata": {
                "source": source_meta.get("source", "unknown"),
                "question_id": f"Q{i}",
                "doc_type": "faq",
                "topic": source_meta.get("topic", [])
            }
        })
    return chunks

# 2. Hierarchical chunking (guidance notes)
def chunk_hierarchical(text: str, source_meta: dict) -> list[dict]:
    # Split by section headings (e.g., Section X:, Section X.Y:, ## Heading)
    sections = re.split(r'(?i)(Section [\d\.]+:[^\n]*|##\s+[^\n]*)', text)
    chunks = []
    
    for i in range(1, len(sections), 2):
        heading = sections[i].strip()
        content = sections[i+1].strip() if i+1 < len(sections) else ""
        if not content: continue
        
        # Parent chunk: full section
        parent_id = f"sec_{i//2}"
        parent = {
            "chunk_id": parent_id,
            "text": f"{heading}\n{content}",
            "metadata": {
                "source": source_meta.get("source", "unknown"),
                "section": heading,
                "chunk_type": "parent",
                "doc_type": "guidance"
            }
        }
        chunks.append(parent)
        
        # Child chunks: recursive split of content with sentence boundaries
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=[
                "\n\n",  # Paragraphs
                "\n",    # Lines
                ". ",    # Sentences (English)
                "। ",    # Sentences (Hindi)
                "? ",    # Questions
                "! ",    # Exclamations
                "; ",    # Clauses
                ", ",    # Sub-clauses
                " ",     # Words
                ""       # Characters
            ]
        )
        child_texts = splitter.split_text(content)
        
        for j, child_text in enumerate(child_texts):
            chunks.append({
                "chunk_id": f"{parent_id}_child_{j:03d}",
                "text": f"{heading} - Context: {child_text}",
                "metadata": {
                    "source": source_meta.get("source", "unknown"),
                    "section": heading,
                    "parent_id": parent_id,
                    "chunk_type": "child",
                    "doc_type": "guidance"
                }
            })
    
    return chunks

# 3. PDF chunking using pypdf (fallback from unstructured)
def chunk_with_tables(pdf_path: str, source_meta: dict) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf not installed. Skipping PDF.")
        return []
        
    chunks = []
    try:
        reader = PdfReader(pdf_path)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=700, 
            chunk_overlap=100,
            separators=[
                "\n\n", "\n", ". ", "। ", "? ", "! ", "; ", ", ", " ", ""
            ]
        )
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text: continue
            
            for j, chunk_text in enumerate(splitter.split_text(text)):
                chunks.append({
                    "chunk_id": f"page_{i:03d}_chunk_{j:02d}",
                    "text": chunk_text,
                    "metadata": {
                        "source": source_meta.get("source", "unknown"),
                        "page": i + 1,
                        "doc_type": "bank_rules",
                        "topic": source_meta.get("topic", [])
                    }
                })
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    
    return chunks

if __name__ == "__main__":
    import glob
    
    raw_dir = os.path.join(os.path.dirname(__file__), "../data/raw")
    output_path = os.path.join(os.path.dirname(__file__), "../data/chunks/retrieval_chunks.jsonl")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    all_chunks = []
    
    # Process all markdown files in data/raw
    for filepath in glob.glob(os.path.join(raw_dir, "*.md")):
        filename = os.path.basename(filepath)
        print(f"Processing {filename}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        meta = {
            "source": filename,
            "topic": ["tax", "fd", "rules"]
        }
        
        if "faq" in filename.lower():
            chunks = chunk_faq(content, meta)
            if not chunks:
                chunks = chunk_hierarchical(content, meta)
        else:
            chunks = chunk_hierarchical(content, meta)
            
        all_chunks.extend(chunks)

    # Process all PDF files in data/
    data_dir = os.path.join(os.path.dirname(__file__), "../data")
    for filepath in glob.glob(os.path.join(data_dir, "*.pdf")):
        filename = os.path.basename(filepath)
        print(f"Processing PDF {filename}...")
        
        meta = {
            "source": filename,
            "topic": ["bank", "fd", "rules"]
        }
        chunks = chunk_with_tables(filepath, meta)
        all_chunks.extend(chunks)
        
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for chunk in all_chunks:
                f.write(json.dumps(chunk) + "\n")
        print(f"Successfully wrote {len(all_chunks)} chunks to {output_path}")
    except Exception as e:
        print(f"Error writing to output: {e}")
