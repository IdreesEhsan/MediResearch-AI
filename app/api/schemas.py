# ============================================================
# app/api/schemas.py
# ============================================================
# Pydantic models for all FastAPI request and response types.
#
# Pydantic automatically:
#   - Validates incoming request data
#   - Converts types (e.g. string → enum)
#   - Generates Swagger documentation
#   - Returns clear error messages for invalid input
# ============================================================

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────
class FocusAreaEnum(str, Enum):
    """Research domain options for the frontend dropdown."""
    GENERAL = "general"
    DISEASE = "disease"
    DRUG = "drug"
    NEWS = "news"
    
class HITLDecisionEnum(str, Enum):
    """Doctor approval decision options."""
    APPROVED = "approved"
    REJECTED = "rejected"
    
class ExportFormatEnum(str, Enum):
    """Export format options."""
    PDF = "pdf"
    WORD = "word"
    
# ── Research Request/Response ─────────────────────────────────

class ResearchStartRequest(BaseModel):
    """
    Request body for POST /research/start
    Starts a new research session.
    """
    query: str = Field(..., min_length=3, max_length=500, description="The medical research question")
    focus_area: FocusAreaEnum = Field(default=FocusAreaEnum.GENERAL, description="Research domain")
    session_id: Optional[str] = Field(default=None, description="Optional custom session ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query":      "What are the treatment options for type 2 diabetes?",
                "focus_area": "disease",
                "session_id": None
            }
        }

class ResearchStatusResponse(BaseModel):
    """
    Response for GET /research/{session_id}/status
    Returns current status of a research session.
    """
    session_id: str
    status: str     # running / paused / completed / failed
    current_agent: Optional[str] = None
    confidence_score: Optional[int] = None
    hitl_decision: Optional[str] = None
    message: str
    
class ResearchStartResponse(BaseModel):
    """
    Response for POST /research/start
    Returns the new session ID and initial status.
    """
    session_id: str
    status: str
    message: str

# ── HITL Approval ─────────────────────────────────────────────
class HITLApprovalRequest(BaseModel):
    """
    Request body for POST /research/{session_id}/approve
    Doctor submits their approval decision.
    """
    decision: HITLDecisionEnum = Field(..., description="Approval to proceed, Rejected to revise")
    comments: Optional[str] = Field(default="", description="Doctor's notes or correction instructions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision": "approved",
                "comments": "Findings are accurate. Good coverage of treatment options."
            }
        }
        
class HITLApprovalResponse(BaseModel):
    """Response for POST /research/{session_id}/approve"""
    session_id: str
    decision:   str
    message:    str

# ── Report ────────────────────────────────────────────────────

class ReportResponse(BaseModel):
    """
    Response for GET /research/{session_id}/report
    Returns the final approved research report.
    """
    session_id:       str
    query:            str
    focus_area:       str
    final_report:     str
    confidence_score: int
    sources:          List[str]
    created_at:       Optional[str] = None
    export_pdf_path:  Optional[str] = None
    export_word_path: Optional[str] = None

# ── Session History ───────────────────────────────────────────

class SessionRecord(BaseModel):
    """
    A single session record from the SQLite database.
    Used in session list and search responses.
    """
    session_id:       str
    query:            str
    focus_area:       str
    confidence_score: Optional[int]  = None
    hitl_approved:    Optional[bool] = None
    created_at:       str
    has_report:       bool = False
    
class SessionDetailResponse(BaseModel):
    """
    Response for GET /sessions/{session_id}
    Returns full details of a past session.
    """
    session_id:       str
    query:            str
    focus_area:       str
    summary:          Optional[str] = None
    final_report:     Optional[str] = None
    confidence_score: Optional[int] = None
    hitl_approved:    Optional[bool] = None
    created_at:       str
    
class SessionListResponse(BaseModel):
    """Response for GET /sessions"""
    sessions: List[SessionRecord]
    total:    int


class SessionSearchResponse(BaseModel):
    """Response for GET /sessions/search"""
    query:    str
    sessions: List[SessionRecord]
    total:    int

# ── Export ────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    """
    Request body for POST /export/pdf and POST /export/word
    Triggers export generation for a session.
    """
    session_id: str = Field(..., description="Session ID to export")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            }
        }
        
class ExportResponse(BaseModel):
    """Response for export endpoints."""
    session_id:  str
    format:      str
    file_path:   Optional[str] = None
    download_url: Optional[str] = None
    status:      str
    message:     str


class ExportStatusResponse(BaseModel):
    """Response for GET /export/status/{session_id}"""
    session_id:  str
    pdf_ready:   bool
    word_ready:  bool
    pdf_path:    Optional[str] = None
    word_path:   Optional[str] = None

# ── Health Check ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response for GET /health"""
    status:    str
    version:   str
    timestamp: str
    services:  Dict[str, str]