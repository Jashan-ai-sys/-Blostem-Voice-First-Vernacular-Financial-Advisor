import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1" # Default Pinecone environment
    PINECONE_INDEX_NAME: str = "financial-knowledge"
    EMBEDDING_MODEL: str = "models/gemini-embedding-2" # Current gemini-embedding model
    GENERATION_MODEL: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"

settings = Settings()
