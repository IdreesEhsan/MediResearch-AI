# ============================================================
# app/graph/state.py
# ============================================================
# ResearchState — the shared data structure passed between
# all 8 LangGraph nodes.
#
# Fields written by multiple parallel agents use Annotated
# with operator.add so LangGraph merges them automatically
# instead of raising InvalidUpdateError.
# ============================================================

import uuid
import operator
from typing import TypedDict, List, Dict, Optional, Any, Annotated
from enum import Enum


class FocusArea(str, Enum):
    GENERAL = "general"
    DISEASE = "disease"
    DRUG    = "drug"
    NEWS    = "news"


class HITLDecision(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResearchState(TypedDict, total=False):
    query: str
    focus_area: FocusArea
    session_id: str

    # Parallel outputs (safe merging)
    search_results: Annotated[List[Dict[str, Any]], operator.add]
    rag_results:    Annotated[List[Dict[str, Any]], operator.add]
    news_results:   Annotated[List[Dict[str, Any]], operator.add]
    sources:        Annotated[List[str], operator.add]

    # Sequential outputs
    summary: str
    fact_check_results: List[Dict[str, Any]]
    confidence_score: int

    # HITL
    hitl_decision: HITLDecision
    hitl_comments: str
    final_report: str

    # Memory
    chat_history: List[Dict[str, Any]]
    context_summary: str
    session_saved: bool

    # Export
    export_pdf_path: Optional[str]
    export_word_path: Optional[str]

    # Control
    error: Optional[str]
    retry_count: int


def initial_state(
    query: str,
    focus_area: str,
    session_id: Optional[str] = None
) -> ResearchState:
    return ResearchState(
        query=query,
        focus_area=FocusArea(focus_area),
        session_id=session_id or str(uuid.uuid4()),

        search_results=[],
        rag_results=[],
        news_results=[],
        sources=[],

        summary="",
        fact_check_results=[],
        confidence_score=0,

        hitl_decision=HITLDecision.PENDING,
        hitl_comments="",
        final_report="",

        chat_history=[],
        context_summary="",
        session_saved=False,

        export_pdf_path=None,
        export_word_path=None,

        error=None,
        retry_count=0,
    )