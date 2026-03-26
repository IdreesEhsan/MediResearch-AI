# ============================================================
# app/utils/config.py
# ============================================================
# Central configuration file for MediResearch AI.
# All settings and API keys are defined here in one place.
#
# How to use in any other file:
#   from app.utils.config import config
#   print(config.GROQ_MODEL)
# ============================================================

import os
from dotenv import load_dotenv

# Read the .env file and load all variables into the environment.
# This must run before any os.getenv() calls.
load_dotenv()

class Config:
    """
    Central config class.
    All environment variables and project settings live here.
    Import the shared instance at the bottom: config = Config()
    """
    # ── Groq (LLM Engine) ────────────────────────────────────
    
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_TEMPERATURE: float = 0.1
    GROQ_MAX_TOKENS: int = 2048
    
    # ── Pinecone (Vector Database) ───────────────────────────
    
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX: str = os.getenv("PINECONE_INDEX", "medical-research-index")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")
    PINECONE_DIMENSION: int = 384
    PINECONE_METRIC: str = "cosine"
    PINECONE_DOCS_NAMESPACE: str = "medical-docs"
    PINECONE_SESSIONS_NAMESPACE: str = "sessions-ns"
    
    # ── Embeddings ───────────────────────────────────────────
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # ── LangSmith (Observability & Tracing) ──────────────────
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_TRACING_V2: str = os.getenv("LANGSMITH_TRACING_V2", "true")
    LANGSMITH_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "MediResearch-AI")
    
    # ── Search ───────────────────────────────────────────────
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
    SEARCH_MAX_RESULTS = 5
    NEWS_LOOKBACK_DAYS = 90
    
    # ── RAG / CRAG ───────────────────────────────────────────
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    TOP_K_RETRIEVAL = 10
    CRAG_RELEVANT_THRESHOLD = 0.7
    CRAG_PARTIAL_THRESHOLD = 0.4
    
    # ── Session Memory ───────────────────────────────────────
    MEMORY_TOP_K = 3
    MEMORY_MAX_CONTEXT_TOKENS = 300
    SESSION_DB_PATH = "mediresearch.db"
    
    # ── Export ───────────────────────────────────────────────
    EXPORT_CACHE_DIR = "exports"
    EXPORT_CACHE_HOURS = 24
    
    # ── FastAPI ──────────────────────────────────────────────
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_TITLE = "MediResearch AI API"
    API_VERSION = "2.0.0"
    
    def validate(self):
        """Check all required keys are set. Call this at startup."""
        required = {
            "GROQ_API_KEY":      self.GROQ_API_KEY,
            "PINECONE_API_KEY":  self.PINECONE_API_KEY,
            "LANGSMITH_API_KEY": self.LANGSMITH_API_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please check your .env file."
            )
            
# Single shared instance — import this everywhere
# Usage:  from app.utils.config import config
config = Config()