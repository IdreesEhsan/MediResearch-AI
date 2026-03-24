# ============================================================
# app/api/routes.py
# ============================================================
# All 11 FastAPI endpoints for MediResearch AI.
#
# Endpoints:
#   POST   /research/start           Start new research session
#   GET    /research/{id}/status     Check session status
#   POST   /research/{id}/approve    HITL approval/rejection
#   GET    /research/{id}/report     Get final report
#   GET    /sessions                 List all sessions
#   GET    /sessions/search          Search sessions
#   GET    /sessions/{id}            Get one session
#   DELETE /sessions/{id}            Delete a session
#   POST   /export/pdf               Generate PDF
#   POST   /export/word              Generate Word
#   GET    /health                   Health check
# ============================================================

import uuid
import sqlite3
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.api.schemas import (
    ResearchStartRequest, ResearchStartResponse,
    ResearchStatusResponse, HITLApprovalRequest,
    HITLApprovalResponse, ReportResponse,
    SessionRecord, SessionListResponse,
    SessionDetailResponse, SessionSearchResponse,
    ExportRequest, ExportResponse, ExportStatusResponse,
    HealthResponse
)
from app.utils.config import config

# ── Router ────────────────────────────────────────────────────
# APIRouter groups all endpoints together
# Imported and mounted in main.py
router = APIRouter()

# ── In-memory session store ───────────────────────────────────
# Stores active research sessions and their states
# Key: session_id, Value: ResearchState dict
active_sessions: dict = {}

# ── Helper: Get DB connection ─────────────────────────────────

def get_db():
    """
    Get a SQLite database connection.
    Always close the connection after use.
    """
    return sqlite3.connect(config.SESSION_DB_PATH)

# ── Helper: Run research in background ───────────────────────

def run_research_background(
    session_id: str,
    query: str,
    focus_area: str
) -> None:
    """
    Run the research workflow in a background thread.
    Updates active_sessions with results when complete.

    Args:
        session_id: Unique session identifier.
        query:      Research question.
        focus_area: Research domain.
    """
    try:
        # Mark session as running
        active_sessions[session_id]["status"] = "running"
        active_sessions[session_id]["current_agent"] = "memory_load"
        
        # Import here to avoid circular imports
        from app.graph.workflow import run_research

        # Run the full pipeline
        result = run_research(
            query=query,
            focus_area=focus_area,
            session_id=session_id,
            auto_approve=False   # Real HITL — wait for doctor
        )
        
        # Store result in active sessions
        active_sessions[session_id].update({
            "status":           "paused",   # Paused at HITL
            "current_agent":    "hitl_node",
            "state":            result,
            "confidence_score": result.get("confidence_score", 0),
            "summary":          result.get("summary", ""),
        })

    except Exception as e:
        active_sessions[session_id]["status"]  = "failed"
        active_sessions[session_id]["error"]   = str(e)
        print(f"❌ Background research failed: {e}")
        

# ════════════════════════════════════════════════════════════════
# RESEARCH ENDPOINTS
# ════════════════════════════════════════════════════════════════

@router.post("/research/start", response_model=ResearchStartResponse)
async def start_research(
    request: ResearchStartRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new medical research session.

    The research runs in the background — use
    GET /research/{session_id}/status to track progress.
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    # Initialize session in active store
    active_sessions[session_id] = {
        "session_id":  session_id,
        "query":       request.query,
        "focus_area":  request.focus_area,
        "status":      "starting",
        "created_at":  datetime.now().isoformat(),
    }
    
    # Run research in background so API returns immediately
    background_tasks.add_task(
        run_research_background,
        session_id = session_id,
        query      = request.query,
        focus_area = request.focus_area.value
    )

    return ResearchStartResponse(
        session_id = session_id,
        status     = "starting",
        message    = f"Research started. Use GET /research/{session_id}/status to track progress."
    )
    
@router.get("/research/{session_id}/status", response_model=ResearchStatusResponse)
async def get_research_status(session_id: str):
    """
    Check the current status of a research session.

    Status values:
        starting  → Just created
        running   → Agents are working
        paused    → Waiting for HITL doctor approval
        completed → Research finished
        failed    → An error occurred
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    return ResearchStatusResponse(
        session_id       = session_id,
        status           = session.get("status", "unknown"),
        current_agent    = session.get("current_agent"),
        confidence_score = session.get("confidence_score"),
        hitl_decision    = session.get("hitl_decision"),
        message          = f"Session is {session.get('status', 'unknown')}"
    )
    
@router.post("/research/{session_id}/approve", response_model=HITLApprovalResponse)
async def approve_research(
    session_id: str,
    request: HITLApprovalRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit doctor's HITL approval or rejection.

    APPROVED → workflow resumes and generates final report
    REJECTED → workflow loops back with doctor's notes
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    if session.get("status") != "paused":
        raise HTTPException(
            status_code=400,
            detail="Session is not waiting for approval"
        )
        
     # Update session with doctor's decision
    active_sessions[session_id]["hitl_decision"] = request.decision.value
    active_sessions[session_id]["hitl_comments"] = request.comments
    active_sessions[session_id]["status"]        = "resuming"

    # Resume workflow in background with doctor's decision
    def resume_workflow():
        try:
            from app.graph.state import HITLDecision
            from app.graph.workflow import build_workflow
            
            state = session.get("state", {})
            state["hitl_decision"] = HITLDecision(request.decision.value)
            state["hitl_comments"] = request.comments or ""
            
            app = build_workflow()
            config_dict = {"configurable": {"thread_id": session_id}}
            result = app.invoke(state, config=config_dict)
            
            # Update session with final results
            active_sessions[session_id].update({
                "status":           "completed",
                "current_agent":    "done",
                "state":            result,
                "final_report":     result.get("final_report", ""),
                "confidence_score": result.get("confidence_score", 0),
                "export_pdf_path":  result.get("export_pdf_path"),
                "export_word_path": result.get("export_word_path"),
            })
            
        except Exception as e:
            active_sessions[session_id]["status"] = "failed"
            active_sessions[session_id]["error"]  = str(e)
        
    background_tasks.add_task(resume_workflow)
    
    return HITLApprovalResponse(
        session_id = session_id,
        decision = request.decision.value,
        message = f"Decision '{request.decision.value}' submitted. Workflow resuming."
    )
    
@router.get("/research/{session_id}/report", response_model=ReportResponse)
async def get_report(session_id: str):
    """
    Get the final approved research report for a session.
    Only available after HITL approval and report generation.
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]

    if session.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready yet. Status: {session.get('status')}"
        )
    
    state = session.get("state", {})
    
    return ReportResponse(
        session_id=session_id,
        query=session.get("query", ""),
        focus_area=str(session.get("focus_area", "")),
        final_report=state.get("final_report", ""),
        confidence_score=state.get("confidence_score", 0),
        sources=state.get("sources", []),
        export_pdf_path=state.get("export_pdf_path"),
        export_word_path=state.get("export_word_path"),
    )

# ════════════════════════════════════════════════════════════════
# SESSION ENDPOINTS
# ════════════════════════════════════════════════════════════════

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(limit: int = 20, offset: int = 0):
    """
    List all past research sessions from SQLite.
    Supports pagination with limit and offset.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT session_id, query, focus_area,
                   confidence_score, hitl_approved, created_at,
                   CASE WHEN final_report != '' THEN 1 ELSE 0 END as has_report
            FROM sessions
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total = cursor.fetchone()[0]
        conn.close()
        
        sessions = [
            SessionRecord(
                session_id       = row[0],
                query            = row[1],
                focus_area       = row[2],
                confidence_score = row[3],
                hitl_approved    = bool(row[4]) if row[4] is not None else None,
                created_at       = row[5],
                has_report       = bool(row[6])
            )
            for row in rows
        ]
        
        return SessionListResponse(status_code=500, detail=str(e))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/sessions/search", response_model=SessionSearchResponse)
async def search_sessions(q: str, limit: int = 10):
    """
    Search past sessions by keyword.
    Searches across query text and report content.
    """
    try:
        conn   = get_db()
        cursor = conn.cursor()

        # Search in query field
        cursor.execute("""
            SELECT session_id, query, focus_area,
                   confidence_score, hitl_approved, created_at,
                   CASE WHEN final_report != '' THEN 1 ELSE 0 END as has_report
            FROM sessions
            WHERE LOWER(query) LIKE ?
               OR LOWER(summary) LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (f"%{q.lower()}%", f"%{q.lower()}%", limit))

        rows = cursor.fetchall()
        conn.close()

        sessions = [
            SessionRecord(
                session_id       = row[0],
                query            = row[1],
                focus_area       = row[2],
                confidence_score = row[3],
                hitl_approved    = bool(row[4]) if row[4] is not None else None,
                created_at       = row[5],
                has_report       = bool(row[6])
            )
            for row in rows
        ]

        return SessionSearchResponse(
            query    = q,
            sessions = sessions,
            total    = len(sessions)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """
    Get full details of a specific past session.
    """
    try:
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, query, focus_area, summary,
                   final_report, confidence_score,
                   hitl_approved, created_at
            FROM sessions
            WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionDetailResponse(
            session_id       = row[0],
            query            = row[1],
            focus_area       = row[2],
            summary          = row[3],
            final_report     = row[4],
            confidence_score = row[5],
            hitl_approved    = bool(row[6]) if row[6] is not None else None,
            created_at       = row[7]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a specific session from the database.
    """
    try:
        conn   = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Session not found")

        # Also remove from active sessions if present
        active_sessions.pop(session_id, None)

        return {"session_id": session_id, "deleted": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ════════════════════════════════════════════════════════════════
# EXPORT ENDPOINTS
# ════════════════════════════════════════════════════════════════

@router.post("/export/pdf", response_model=ExportResponse)
async def export_pdf(request: ExportRequest):
    """
    Generate a PDF report for a completed session.
    Returns the file path for download.
    """
    session_id = request.session_id

    # Check active sessions first
    if session_id in active_sessions:
        session = active_sessions[session_id]
        state   = session.get("state", {})

        if not state.get("final_report"):
            raise HTTPException(
                status_code=400,
                detail="No report available. Complete research first."
            )
        try:
            from app.agents.export_agent import generate_pdf
            pdf_path = generate_pdf(
                report        = state.get("final_report", ""),
                query         = session.get("query", ""),
                confidence    = state.get("confidence_score", 0),
                hitl_comments = state.get("hitl_comments", ""),
                session_id    = session_id
            )
            
            return ExportResponse(
                session_id   = session_id,
                format       = "pdf",
                file_path    = pdf_path,
                download_url = f"/export/download/{session_id}/pdf",
                status       = "ready",
                message      = "PDF generated successfully"
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=404, detail="Session not found")

@router.post("/export/word", response_model=ExportResponse)
async def export_word(request: ExportRequest):
    """
    Generate a Word document for a completed session.
    Returns the file path for download.
    """
    session_id = request.session_id

    if session_id in active_sessions:
        session = active_sessions[session_id]
        state   = session.get("state", {})

        if not state.get("final_report"):
            raise HTTPException(
                status_code=400,
                detail="No report available. Complete research first."
            )

        try:
            from app.agents.export_agent import generate_word
            word_path = generate_word(
                report        = state.get("final_report", ""),
                query         = session.get("query", ""),
                confidence    = state.get("confidence_score", 0),
                hitl_comments = state.get("hitl_comments", ""),
                session_id    = session_id
            )
            
            return ExportResponse(
                session_id   = session_id,
                format       = "word",
                file_path    = word_path,
                download_url = f"/export/download/{session_id}/word",
                status       = "ready",
                message      = "Word document generated successfully"
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=404, detail="Session not found")

@router.get("/export/status/{session_id}", response_model=ExportStatusResponse)
async def get_export_status(session_id: str):
    """
    Check if export files are ready for a session.
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session  = active_sessions[session_id]
    state    = session.get("state", {})
    pdf_path = state.get("export_pdf_path")
    word_path = state.get("export_word_path")
    
    return ExportStatusResponse(
        session_id = session_id,
        pdf_ready  = pdf_path is not None,
        word_ready = word_path is not None,
        pdf_path   = pdf_path,
        word_path  = word_path
    )
    
# ════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    API health check endpoint.
    Verifies all services are reachable.
    """
    services = {}

    # Check Pinecone
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=config.PINECONE_API_KEY)
        pc.list_indexes()
        services["pinecone"] = "✅ connected"
    except Exception:
        services["pinecone"] = "❌ disconnected"

    # Check Groq
    try:
        from langchain_groq import ChatGroq
        ChatGroq(api_key=config.GROQ_API_KEY, model=config.GROQ_MODEL)
        services["groq"] = "✅ connected"
    except Exception:
        services["groq"] = "❌ disconnected"
        
    # Check SQLite
    try:
        conn = get_db()
        conn.close()
        services["sqlite"] = "✅ connected"
    except Exception:
        services["sqlite"] = "❌ disconnected"

    # Check Tavily
    services["tavily"] = "✅ configured" if config.TAVILY_API_KEY else "⚠️  key missing"

    return HealthResponse(
        status    = "healthy",
        version   = config.API_VERSION,
        timestamp = datetime.now().isoformat(),
        services  = services
    )