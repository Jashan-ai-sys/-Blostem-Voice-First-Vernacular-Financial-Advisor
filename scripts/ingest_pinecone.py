import json
import uuid
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec
import sys
import os
import time

# Add parent to path to import app.config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings

# ── API Key Rotation ──────────────────────────────────────────────
API_KEYS = [
    "",
    "",
]
current_key_idx = 0

def switch_key():
    """Rotate to the next API key and reconfigure genai."""
    global current_key_idx
    current_key_idx = (current_key_idx + 1) % len(API_KEYS)
    genai.configure(api_key=API_KEYS[current_key_idx])
    print(f"  🔑 Switched to API key #{current_key_idx + 1}")

def main():
    global current_key_idx
    
    if not settings.PINECONE_API_KEY:
        print("Error: PINECONE_API_KEY not set in .env")
        return

    # Start with key 1
    genai.configure(api_key=API_KEYS[current_key_idx])
    print(f"Starting with API key #{current_key_idx + 1}")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    
    index_name = settings.PINECONE_INDEX_NAME
    
    # Create index if it doesn't exist
    if index_name not in pc.list_indexes().names():
        print(f"Creating index {index_name} with dimension=768...")
        pc.create_index(
            name=index_name,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        while not pc.describe_index(index_name).status['ready']:
            time.sleep(1)
            
    index = pc.Index(index_name)
    print(f"Connected to Pinecone index: {index_name}")
    
    # Read chunks
    chunks_file = os.path.join(os.path.dirname(__file__), "../data/chunks/retrieval_chunks.jsonl")
    if not os.path.exists(chunks_file):
        print(f"File {chunks_file} not found. Please run chunk_data.py first.")
        return
        
    vectors = []
    total_upserted = 0
    batch_size = 50  # Upsert every 50 to avoid losing progress
    
    with open(chunks_file, 'r') as f:
        lines = f.readlines()
    
    total = len(lines)
    print(f"Total chunks to embed: {total}\n")
    
    for idx, line in enumerate(lines):
        chunk = json.loads(line)
        text_to_embed = chunk["text"]
        
        success = False
        retries = 0
        while not success and retries < 8:
            try:
                result = genai.embed_content(
                    model=settings.EMBEDDING_MODEL,
                    content=text_to_embed,
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768
                )
                embedding = result['embedding']
                
                point_id = chunk.get("chunk_id", str(uuid.uuid4()))
                
                # Flatten metadata for Pinecone
                flat_meta = {"text": chunk["text"], "chunk_id": point_id}
                if "metadata" in chunk:
                    for k, v in chunk["metadata"].items():
                        if isinstance(v, list):
                            flat_meta[k] = ", ".join(str(x) for x in v)
                        else:
                            flat_meta[k] = v
                            
                vectors.append({
                    "id": point_id,
                    "values": embedding,
                    "metadata": flat_meta
                })
                print(f"[{idx+1}/{total}] Embedded: {point_id}")
                success = True
                time.sleep(0.6)  # ~100 req/min safe
            except Exception as e:
                err = str(e)
                if "429" in err:
                    print(f"  ⚠️  Rate limit on key #{current_key_idx + 1}. Switching...")
                    switch_key()
                    retries += 1
                elif "503" in err or "Timeout" in err or "handshaker" in err:
                    print(f"  🌐 Network error, retrying in 15s... ({retries+1}/8)")
                    time.sleep(15)
                    retries += 1
                else:
                    print(f"  ❌ Failed chunk {chunk.get('chunk_id')}: {e}")
                    break
        
        # Incremental upsert every batch_size chunks
        if len(vectors) >= batch_size:
            index.upsert(vectors=vectors)
            total_upserted += len(vectors)
            print(f"  ✅ Upserted batch ({total_upserted}/{total} total)")
            vectors = []
    
    # Final upsert for remaining vectors
    if vectors:
        index.upsert(vectors=vectors)
        total_upserted += len(vectors)
    
    print(f"\n🎉 Done! Successfully ingested {total_upserted}/{total} chunks into Pinecone.")

if __name__ == "__main__":
    main()
