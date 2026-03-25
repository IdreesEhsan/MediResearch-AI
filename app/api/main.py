# ============================================================
# app/api/main.py
# ============================================================
# FastAPI application entry point.
#
# Starts the API server with:
#   - All 11 routes mounted
#   - CORS enabled for Streamlit frontend
#   - LangSmith tracing initialized
#   - Database initialized on startup
#   - Swagger docs at http://localhost:8000/docs
#
# Run with:
#   uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from app.utils.config import config
from app.utils.langsmith_config import setup_langsmith
from app.api.routes import router

# ── Lifespan ──────────────────────────────────────────────────
# Runs startup and shutdown logic for the FastAPI app

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown handler.

    ON STARTUP:
        - Validate all API keys are present
        - Initialize SQLite database tables
        - Enable LangSmith tracing
        - Pre-load embedding model

    ON SHUTDOWN:
        - Clean up resources
    """
    
    # ── Startup ───────────────────────────────────────────────
    print("\n" + "="*55)
    print("🏥 MediResearch AI — API Starting Up")
    print("="*55)

    # Step 1: Validate all required API keys
    try:
        config.validate()
        print("✅ API keys validated")
    except EnvironmentError as e:
        print(f"❌ {e}")
        raise
    
    # Step 2: Initialize database
    try:
        from app.agents.memory_agent import init_database
        init_database()
    except Exception as e:
        print(f"⚠️  Database init warning: {e}")

    # Step 3: Enable LangSmith tracing
    setup_langsmith()
    
    # Step 4: Pre-load embedding model so first request is fast
    try:
        from app.rag.embeddings import embedder
        print(f"✅ Embedding model ready")
    except Exception as e:
        print(f"⚠️  Embedding model warning: {e}")

    # Step 5: Create exports directory
    os.makedirs(config.EXPORT_CACHE_DIR, exist_ok=True)
    print(f"✅ Export directory ready: {config.EXPORT_CACHE_DIR}/")

    print("="*55)
    print(f"🚀 API ready at http://{config.API_HOST}:{config.API_PORT}")
    print(f"📖 Swagger docs at http://localhost:{config.API_PORT}/docs")
    print("="*55 + "\n")

    yield # App runs here
    
    # ── Shutdown ──────────────────────────────────────────────
    print("\n🛑 MediResearch AI — API Shutting Down")


# ── Create FastAPI App ────────────────────────────────────────
app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description="""
    ## MediResearch AI API

    Multi-Agent Medical Research Assistant powered by LangGraph,
    Groq LLaMA 3.3 70B, Pinecone, and CRAG.

    ### Features
    - 🔍 **Real-time web search** via Tavily
    - 📚 **Knowledge base retrieval** with CRAG validation
    - 📰 **Latest medical news** aggregation
    - ✅ **AI fact-checking** with confidence scoring
    - 👨‍⚕️ **HITL doctor approval** gate
    - 📄 **PDF & Word export** of final reports
    - 🧠 **Session memory** across research sessions

    ### How to use
    1. `POST /research/start` — start a new research session
    2. `GET /research/{id}/status` — poll until status is `paused`
    3. `POST /research/{id}/approve` — submit doctor approval
    4. `GET /research/{id}/report` — retrieve final report
    5. `POST /export/pdf` or `/export/word` — download report
    """,
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────
# Required for Streamlit frontend to call the API
# In production restrict origins to your actual domain

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],        # Allow all origins in development
    allow_credentials = True,
    allow_methods     = ["*"],        # Allow all HTTP methods
    allow_headers     = ["*"],        # Allow all headers
)

# ── Mount Routes ──────────────────────────────────────────────
# All 11 endpoints defined in routes.py
app.include_router(router, tags=["MediResearch  AI"])

# ── File Download Endpoint ────────────────────────────────────
@app.get("/export/download/{session_id}/{format}")
async def download_export(session_id: str, format: str):
    """
    Download a generated export file.

    Args:
        session_id: The research session ID.
        format:     'pdf' or 'word'
    """
    from app.api.routes import active_sessions
    
    if session_id not in active_sessions:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = active_sessions[session_id].get("state", {})
    
    if format == "pdf":
        file_path = state.get("export_pdf_path")
        media_type = "application/pdf"
        filename   = f"mediresearch_report_{session_id[:8]}.pdf"

    elif format == "word":
        file_path  = state.get("export_word_path")
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename   = f"mediresearch_report_{session_id[:8]}.docx"

    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid format. Use 'pdf' or 'word'")

    if not file_path or not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Export file not found")

    # Stream the file to the client
    return FileResponse(
        path             = file_path,
        media_type       = media_type,
        filename         = filename
    )
    
# ── Root Endpoint ─────────────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint — confirms API is running."""
    return {
        "name":    "MediResearch AI API",
        "version": config.API_VERSION,
        "status":  "running",
        "docs":    "/docs",
        "health":  "/health"
    }