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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.utils.config import config
from app.utils.langsmith_config import setup_langsmith
from app.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*55)
    print("🏥 MediResearch AI — API Starting Up")
    print("="*55)

    try:
        config.validate()
        print("✅ API keys validated")
    except EnvironmentError as e:
        print(f"❌ {e}")
        raise

    # Initialize database
    try:
        from app.agents.memory_agent import init_database
        init_database()
    except Exception as e:
        print(f"⚠️ Database init warning: {e}")

    setup_langsmith()

    # Pre-load embedding model
    try:
        from app.rag.embeddings import embedder
        print("✅ Embedding model ready")
    except Exception as e:
        print(f"⚠️ Embedding model warning: {e}")

    os.makedirs(config.EXPORT_CACHE_DIR, exist_ok=True)
    print(f"✅ Export directory ready: {config.EXPORT_CACHE_DIR}/")

    print("="*55)
    print(f"🚀 API ready at http://{config.API_HOST}:{config.API_PORT}")
    print(f"📖 Swagger docs at http://localhost:{config.API_PORT}/docs")
    print("="*55 + "\n")

    yield
    print("\n🛑 MediResearch AI — API Shutting Down")


app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description="MediResearch AI - Multi-Agent Medical Research Assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend folder as static files
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# Include API routes
app.include_router(router, tags=["MediResearch AI"])

# Root redirect to frontend
@app.get("/")
async def root():
    return {"message": "MediResearch AI API is running", "frontend": "/frontend/index.html"}

# File download endpoint (already existed)
@app.get("/export/download/{session_id}/{format}")
async def download_export(session_id: str, format: str):
    from app.api.routes import active_sessions
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = active_sessions[session_id].get("state", {})
    
    if format == "pdf":
        file_path = state.get("export_pdf_path")
        media_type = "application/pdf"
        filename = f"mediresearch_report_{session_id[:8]}.pdf"
    elif format == "word":
        file_path = state.get("export_word_path")
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"mediresearch_report_{session_id[:8]}.docx"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(path=file_path, media_type=media_type, filename=filename)