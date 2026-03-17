# ============================================================
# app/graph/state.py
# ============================================================
# ResearchState — the single shared object that flows through
# all 8 LangGraph nodes.
#
# Every agent reads from this state and writes back only the
# fields it updates. LangGraph merges everything automatically.
# ============================================================

import uuid
from typing import TypedDict, List, Dict, Optional, Any
from enum import Enum

# ── Enums ─────────────────────────────────────────────────────

class FocusArea(str, Enum):
    """
    The four supported research domains.
    Used by the router to configure agent behaviour.
    """
    GENERAL = "general"   # General medical Q&A
    DISEASE = "disease"   # Disease-specific research
    DRUG    = "drug"      # Drug and treatment research
    NEWS    = "news"      # Latest medical news
    
class HITLDecision(str, Enum):
    """
    Possible outcomes from the doctor approval gate.
    """
    PENDING  = "pending"   # Doctor has not reviewed yet
    APPROVED = "approved"  # Doctor approved — proceed to report
    REJECTED = "rejected"  # Doctor rejected — loop back with notes

# ── State ─────────────────────────────────────────────────────

class ResearchState(TypedDict, total=False):
    """
    Central state object shared across all 8 LangGraph nodes.

    total=False means all fields are optional — each agent only
    needs to return the fields it changed. LangGraph handles
    merging the rest automatically.

    ── INPUT ────────────────────────────────────────────────
    query:        The user's research question
    focus_area:   Research domain (general/disease/drug/news)
    session_id:   Unique ID for this research session

    ── PHASE 1 — PARALLEL OUTPUTS ───────────────────────────
    search_results:  Results from Search Agent
    rag_results:     Validated chunks from RAG Agent
    news_results:    Latest news from News Agent
    sources:         All source references collected
    
     ── PHASE 2 — SEQUENTIAL OUTPUTS ─────────────────────────
    summary:             Merged summary from Summarizer Agent
    fact_check_results:  Validated claims from Fact-Check Agent
    confidence_score:    Overall score 0-100

    ── PHASE 3 — HITL ───────────────────────────────────────
    hitl_decision:  PENDING / APPROVED / REJECTED
    hitl_comments:  Doctor notes and corrections
    final_report:   Final Markdown report

    ── MEMORY AGENT (new feature) ───────────────────────────
    chat_history:    Prior session records
    context_summary: Summarized prior context to inject
    session_saved:   True once session is saved to SQLite

    ── EXPORT AGENT (new feature) ───────────────────────────
    export_pdf_path:  Path to generated PDF file
    export_word_path: Path to generated Word file
    
     ── ERROR HANDLING ────────────────────────────────────────
    error:        Error message if an agent fails
    retry_count:  How many times workflow has looped back
    """
    
    # Input Fields
    query: str
    focus_area: FocusArea
    session_id: str
    
    # Phase 1 — parallel agent outputs
    search_results: List[Dict[str, Any]]  # [{title, url, snippet}]
    rag_results:    List[Dict[str, Any]]  # [{text, source, score}]
    news_results:   List[Dict[str, Any]]  # [{title, url, date, summary}]
    sources:        List[str]             # All source references

    # Phase 2 — sequential agent outputs
    summary:            str
    fact_check_results: List[Dict[str, Any]]  # [{claim, status, source, note}]
    confidence_score:   int                   # 0 to 100

    # Phase 3 — HITL
    hitl_decision: HITLDecision
    hitl_comments: str
    final_report:  str
    
    # Memory Agent fields
    chat_history:    List[Dict[str, Any]]  # Prior session records
    context_summary: str                   # Summarized prior context
    session_saved:   bool                  # True once saved to SQLite

    # Export Agent fields
    export_pdf_path:  Optional[str]   # Path to generated PDF
    export_word_path: Optional[str]   # Path to generated Word file

    # Error handling
    error:       Optional[str]  # Error message if something fails
    retry_count: int            # Increments each time doctor rejects
    
# ── Factory Function ──────────────────────────────────────────

def initial_state(query: str, focus_area: str, session_id: str = None) -> ResearchState:
    """
    Create a fresh ResearchState with all default values.
    Call this at the start of every new research session.

    Args:
        query:      The user's research question.
        focus_area: One of: general / disease / drug / news
        session_id: Optional UUID — generated automatically if not provided.

    Returns:
        Fully initialized ResearchState ready for the workflow.
    """
    return ResearchState(
        # Input
        query      = query,
        focus_area = FocusArea(focus_area),
        session_id = session_id or str(uuid.uuid4()),

        # Phase 1 — empty lists to start
        search_results = [],
        rag_results    = [],
        news_results   = [],
        sources        = [],

        # Phase 2 — empty to start
        summary            = "",
        fact_check_results = [],
        confidence_score   = 0,

        # HITL — pending until doctor reviews
        hitl_decision = HITLDecision.PENDING,
        hitl_comments = "",
        final_report  = "",

        # Memory — empty until Memory Agent loads history
        chat_history    = [],
        context_summary = "",
        session_saved   = False,

        # Export — None until Export Agent generates files
        export_pdf_path  = None,
        export_word_path = None,

        # Error handling
        error       = None,
        retry_count = 0,
    )