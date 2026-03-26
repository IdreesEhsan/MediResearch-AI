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

router = APIRouter()

# In-memory store for active sessions
active_sessions: dict = {}

def get_db():
    return sqlite3.connect(config.SESSION_DB_PATH)

# ── Background Research Runner ───────────────────────────────
def run_research_background(session_id: str, query: str, focus_area: str):
    try:
        active_sessions[session_id]["status"] = "running"
        active_sessions[session_id]["current_agent"] = "memory_load"

        from app.graph.workflow import run_research

        # No HITL — run fully automatically
        result = run_research(
            query=query,
            focus_area=focus_area,
            session_id=session_id
        )

        active_sessions[session_id].update({
            "status": "completed",
            "current_agent": "done",
            "state": result,
            "confidence_score": result.get("confidence_score", 0),
            "summary": result.get("summary", ""),
            "final_report": result.get("final_report", ""),
            "export_pdf_path": result.get("export_pdf_path"),
            "export_word_path": result.get("export_word_path"),
        })

    except Exception as e:
        active_sessions[session_id]["status"] = "failed"
        active_sessions[session_id]["error"] = str(e)
        print(f"❌ Background research failed: {e}")
        
# ════════════════════════════════════════════════════════════════
# RESEARCH ENDPOINTS
# ════════════════════════════════════════════════════════════════

@router.post("/research/start", response_model=ResearchStartResponse)
async def start_research(request: ResearchStartRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id or str(uuid.uuid4())

    active_sessions[session_id] = {
        "session_id": session_id,
        "query": request.query,
        "focus_area": request.focus_area,
        "status": "starting",
        "created_at": datetime.now().isoformat(),
    }

    background_tasks.add_task(
        run_research_background,
        session_id=session_id,
        query=request.query,
        focus_area=request.focus_area.value
    )

    return ResearchStartResponse(
        session_id=session_id,
        status="starting",
        message=f"Research started. Use GET /research/{session_id}/status to track progress."
    )


@router.get("/research/{session_id}/status", response_model=ResearchStatusResponse)
async def get_research_status(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    return ResearchStatusResponse(
        session_id=session_id,
        status=session.get("status", "unknown"),
        current_agent=session.get("current_agent"),
        confidence_score=session.get("confidence_score"),
        hitl_decision=session.get("hitl_decision"),
        message=f"Session is {session.get('status', 'unknown')}"
    )


@router.post("/research/{session_id}/approve", response_model=HITLApprovalResponse)
async def approve_research(session_id: str, request: HITLApprovalRequest, background_tasks: BackgroundTasks):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    if session.get("status") != "paused":
        raise HTTPException(status_code=400, detail="Session is not waiting for approval")

    session["hitl_decision"] = request.decision.value
    session["hitl_comments"] = request.comments or ""
    session["status"] = "resuming"

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

            session.update({
                "status": "completed",
                "current_agent": "done",
                "state": result,
                "final_report": result.get("final_report", ""),
                "confidence_score": result.get("confidence_score", 0),
                "export_pdf_path": result.get("export_pdf_path"),
                "export_word_path": result.get("export_word_path"),
            })
        except Exception as e:
            session["status"] = "failed"
            session["error"] = str(e)

    background_tasks.add_task(resume_workflow)

    return HITLApprovalResponse(
        session_id=session_id,
        decision=request.decision.value,
        message=f"Decision '{request.decision.value}' submitted. Workflow resuming."
    )


@router.get("/research/{session_id}/report", response_model=ReportResponse)
async def get_report(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]
    if session.get("status") != "completed":
        raise HTTPException(status_code=400, detail=f"Report not ready. Status: {session.get('status')}")

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
# SESSION ENDPOINTS (Fixed)
# ════════════════════════════════════════════════════════════════

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(limit: int = 20, offset: int = 0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT session_id, query, focus_area, confidence_score, 
                   hitl_approved, created_at,
                   CASE WHEN final_report != '' THEN 1 ELSE 0 END as has_report
            FROM sessions
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total = cursor.fetchone()[0]
        conn.close()

        sessions = [
            SessionRecord(
                session_id=row[0],
                query=row[1],
                focus_area=row[2],
                confidence_score=row[3],
                hitl_approved=bool(row[4]) if row[4] is not None else None,
                created_at=row[5],
                has_report=bool(row[6])
            )
            for row in rows
        ]

        return SessionListResponse(sessions=sessions, total=total)   # ← Fixed

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/search", response_model=SessionSearchResponse)
async def search_sessions(q: str, limit: int = 10):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT session_id, query, focus_area, confidence_score,
                   hitl_approved, created_at,
                   CASE WHEN final_report != '' THEN 1 ELSE 0 END as has_report
            FROM sessions
            WHERE LOWER(query) LIKE ? OR LOWER(summary) LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (f"%{q.lower()}%", f"%{q.lower()}%", limit))

        rows = cursor.fetchall()
        conn.close()

        sessions = [
            SessionRecord(
                session_id=row[0],
                query=row[1],
                focus_area=row[2],
                confidence_score=row[3],
                hitl_approved=bool(row[4]) if row[4] is not None else None,
                created_at=row[5],
                has_report=bool(row[6])
            )
            for row in rows
        ]

        return SessionSearchResponse(query=q, sessions=sessions, total=len(sessions))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    try:
        conn = get_db()
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
            session_id=row[0],
            query=row[1],
            focus_area=row[2],
            summary=row[3],
            final_report=row[4],
            confidence_score=row[5],
            hitl_approved=bool(row[6]) if row[6] is not None else None,
            created_at=row[7]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted == 0:
            raise HTTPException(status_code=404, detail="Session not found")

        active_sessions.pop(session_id, None)
        return {"session_id": session_id, "deleted": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════
# EXPORT + HEALTH (unchanged but cleaned)
# ════════════════════════════════════════════════════════════════

@router.post("/export/pdf", response_model=ExportResponse)
async def export_pdf(request: ExportRequest):
    # ... (same as before, but using **state)
    # I kept your original logic here for now
    session_id = request.session_id
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    state = session.get("state", {})

    if not state.get("final_report"):
        raise HTTPException(status_code=400, detail="No report available")

    try:
        from app.agents.export_agent import generate_pdf
        pdf_path = generate_pdf(
            report=state.get("final_report", ""),
            query=session.get("query", ""),
            confidence=state.get("confidence_score", 0),
            hitl_comments=session.get("hitl_comments", ""),
            session_id=session_id
        )
        return ExportResponse(
            session_id=session_id,
            format="pdf",
            file_path=pdf_path,
            download_url=f"/export/download/{session_id}/pdf",
            status="ready",
            message="PDF generated successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/word", response_model=ExportResponse)
async def export_word(request: ExportRequest):
    # Similar logic as PDF
    session_id = request.session_id
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    state = session.get("state", {})

    if not state.get("final_report"):
        raise HTTPException(status_code=400, detail="No report available")

    try:
        from app.agents.export_agent import generate_word
        word_path = generate_word(
            report=state.get("final_report", ""),
            query=session.get("query", ""),
            confidence=state.get("confidence_score", 0),
            hitl_comments=session.get("hitl_comments", ""),
            session_id=session_id
        )
        return ExportResponse(
            session_id=session_id,
            format="word",
            file_path=word_path,
            download_url=f"/export/download/{session_id}/word",
            status="ready",
            message="Word document generated successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/status/{session_id}", response_model=ExportStatusResponse)
async def get_export_status(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = active_sessions[session_id]
    state = session.get("state", {})
    return ExportStatusResponse(
        session_id=session_id,
        pdf_ready=state.get("export_pdf_path") is not None,
        word_ready=state.get("export_word_path") is not None,
        pdf_path=state.get("export_pdf_path"),
        word_path=state.get("export_word_path")
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    # Your original health check is fine
    services = {}
    # ... (keep your existing health check code)
    return HealthResponse(
        status="healthy",
        version=config.API_VERSION,
        timestamp=datetime.now().isoformat(),
        services=services
    )