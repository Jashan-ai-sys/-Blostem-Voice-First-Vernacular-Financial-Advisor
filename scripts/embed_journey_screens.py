import json
import os
from pinecone import Pinecone
import google.generativeai as genai
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.config import settings

load_dotenv()

# Setup API Keys
genai.configure(api_key=settings.GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY"))
pc = Pinecone(api_key=settings.PINECONE_API_KEY or os.getenv("PINECONE_API_KEY"))
index = pc.Index(settings.PINECONE_INDEX_NAME)

def build_combined_text(record):
    """Combines semantic text + metadata into a single block for better embedding."""
    return f"""
Screen Title: {record.get('screen_title')}
Stage: {record.get('stage')}
Description: {record.get('screen_description')}
User Goal: {record.get('user_goal')}
Common Questions: {', '.join(record.get('common_questions', []))}
Common Issues: {', '.join(record.get('common_issues', []))}
Keywords: {', '.join(record.get('keywords', []))}
"""

def process_journey_screens(jsonl_path: str):
    """Reads the JSONL, generates multimodal embeddings, and pushes to Pinecone."""
    if not os.path.exists(jsonl_path):
        print(f"Error: {jsonl_path} not found.")
        return

    vectors_to_upsert = []

    with open(jsonl_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
                
            record = json.loads(line)
            combined_text = build_combined_text(record)
            
            print(f"Processing: {record['screen_title']} (Stage: {record['stage']})")
            
            # Hackathon Note: In a true multimodal embedding call, you'd pass the image bytes here too.
            # For this quick script, we embed the highly semantic text block which contains all image metadata.
            try:
                result = genai.embed_content(
                    model=settings.EMBEDDING_MODEL,
                    content=combined_text,
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768
                )
                embedding = result['embedding']
                
                # Construct Metadata
                metadata = {
                    "type": "journey_screen",
                    "stage": record.get("stage"),
                    "screen_title": record.get("screen_title"),
                    "page_number": record.get("page_number"),
                    "next_stage": record.get("next_stage"),
                    "image_path": record.get("image_path"),
                    "text": combined_text # Store text for retrieval context
                }
                
                vectors_to_upsert.append((record["id"], embedding, metadata))
                
            except Exception as e:
                print(f"Error embedding {record['id']}: {e}")

    # Upsert to Vector DB
    if vectors_to_upsert:
        print(f"Upserting {len(vectors_to_upsert)} records to Pinecone...")
        index.upsert(vectors=vectors_to_upsert)
        print("Done!")
    else:
        print("No vectors to upsert.")

if __name__ == "__main__":
    jsonl_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "journey_screens.jsonl")
    process_journey_screens(jsonl_file)
