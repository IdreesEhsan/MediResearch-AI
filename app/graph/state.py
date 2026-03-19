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


# ── Enums ─────────────────────────────────────────────────────

class FocusArea(str, Enum):
    GENERAL = "general"
    DISEASE = "disease"
    DRUG    = "drug"
    NEWS    = "news"


class HITLDecision(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ── State ─────────────────────────────────────────────────────

class ResearchState(TypedDict, total=False):
    """
    Central state object shared across all 8 LangGraph nodes.

    Fields marked with Annotated + operator.add are LIST fields
    that can be safely written by multiple parallel agents at
    the same time — LangGraph merges them by concatenation.

    All other fields are written by only one agent at a time.
    """

    # ── Input ─────────────────────────────────────────────────
    query:      str
    focus_area: FocusArea
    session_id: str

    # ── Phase 1 outputs ───────────────────────────────────────
    # Annotated with operator.add so parallel agents can all
    # append to these lists without conflicting with each other
    search_results: Annotated[List[Dict[str, Any]], operator.add]
    rag_results:    Annotated[List[Dict[str, Any]], operator.add]
    news_results:   Annotated[List[Dict[str, Any]], operator.add]

    # Sources collected from all agents — merged by concatenation
    sources: Annotated[List[str], operator.add]

    # ── Phase 2 outputs ───────────────────────────────────────
    # These are written by one agent at a time — no annotation needed
    summary:            str
    fact_check_results: List[Dict[str, Any]]
    confidence_score:   int

    # ── HITL ──────────────────────────────────────────────────
    hitl_decision: HITLDecision
    hitl_comments: str
    final_report:  str

    # ── Memory Agent ──────────────────────────────────────────
    chat_history:    List[Dict[str, Any]]
    context_summary: str
    session_saved:   bool

    # ── Export Agent ──────────────────────────────────────────
    export_pdf_path:  Optional[str]
    export_word_path: Optional[str]

    # ── Error handling ────────────────────────────────────────
    error:       Optional[str]
    retry_count: int


# ── Factory Function ──────────────────────────────────────────

def initial_state(
    query: str,
    focus_area: str,
    session_id: str = None
) -> ResearchState:
    """
    Create a fresh ResearchState with all default values.

    Args:
        query:      The user's research question.
        focus_area: One of: general / disease / drug / news
        session_id: Optional UUID — generated if not provided.

    Returns:
        Fully initialized ResearchState.
    """
    return ResearchState(
        # Input
        query      = query,
        focus_area = FocusArea(focus_area),
        session_id = session_id or str(uuid.uuid4()),

        # Phase 1 — empty lists
        search_results = [],
        rag_results    = [],
        news_results   = [],
        sources        = [],

        # Phase 2 — empty
        summary            = "",
        fact_check_results = [],
        confidence_score   = 0,

        # HITL — pending
        hitl_decision = HITLDecision.PENDING,
        hitl_comments = "",
        final_report  = "",

        # Memory — empty
        chat_history    = [],
        context_summary = "",
        session_saved   = False,

        # Export — none yet
        export_pdf_path  = None,
        export_word_path = None,

        # Error handling
        error       = None,
        retry_count = 0,
    )