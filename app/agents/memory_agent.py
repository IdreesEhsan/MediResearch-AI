# ============================================================
# app/agents/memory_agent.py
# ============================================================
# Memory Agent — Runs twice per workflow:
#
#   1. PRE-PHASE 1: Loads relevant past sessions from SQLite
#      and injects summarized context into the state so the
#      Summarizer Agent can build on prior research.
#
#   2. POST-REPORT: Saves the current session to SQLite
#      after the final report is generated.
#
# This transforms MediResearch AI from a single-query tool
# into a persistent research companion.
# ============================================================

import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.utils.config import config
from app.utils.prompts import MEMORY_SUMMARIZER_PROMPT
from app.graph.state import ResearchState

# ── LLM Setup ─────────────────────────────────────────────────
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=0.0,    # Deterministic for context summarization
    max_tokens=500      # Keep context injection short
)

# ── Database Setup ────────────────────────────────────────────

def init_database() -> None:
    """
    Create the SQLite database and sessions table if they
    do not already exist.

    Call this once at application startup.
    The database file is created at config.SESSION_DB_PATH.
    """
    conn = sqlite3.connect(config.SESSION_DB_PATH)
    cursor = conn.cursor()
    
    # Create sessions table to store all research sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id       TEXT PRIMARY KEY,
            query            TEXT NOT NULL,
            focus_area       TEXT NOT NULL,
            summary          TEXT,
            final_report     TEXT,
            source_urls      TEXT,
            confidence_score INTEGER,
            hitl_approved    INTEGER,
            created_at       TEXT NOT NULL
        )
    """)
    
    # Create exports table to track generated PDF/Word files
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exports (
            export_id       TEXT PRIMARY KEY,
            session_id      TEXT NOT NULL,
            format          TEXT NOT NULL,  -- 'pdf' or 'word'
            file_path       TEXT,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized")
    
# ── Save Session ──────────────────────────────────────────────

def save_session(state: ResearchState) -> bool:
    """
    Save the current research session to SQLite.

    Called by the Memory Agent after the Report Agent
    generates the final report.

    Args:
        state: Current ResearchState with completed research.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        conn = sqlite3.connect(config.SESSION_DB_PATH)
        cursor = conn.cursor()
        
        # Convert sources list to JSON string for storage
        sources_json = json.dumps(state.get('sources', []))
        
        # Check if HITL was approved
        hitl_approved = 1 if str(state.get("hitl_decision", "")) == "approved" else 0
        
        cursor.execute("""
            INSERT OR REPLACE INTO sessions
            (session_id, query, focus_area, summary, final_report,
             source_urls, confidence_score, hitl_approved, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state.get("session_id", str(uuid.uuid4())),
            state.get("query", ""),
            str(state.get("focus_area", "general")),
            state.get("summary", ""),
            state.get("final_report", ""),
            sources_json,
            state.get("confidence_score", 0),
            hitl_approved,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"❌ Failed to save session: {e}")
        return False
    
# ── Load Past Sessions ────────────────────────────────────────

def load_similar_sessions(query: str, limit: int = None) -> List[Dict[str, Any]]:
    """
    Load past sessions that might be relevant to the current query.

    Uses simple keyword matching to find related sessions.
    In a production system this would use vector similarity search.

    Args:
        query: The current research question.
        limit: Max sessions to return (default from config).

    Returns:
        List of session dicts sorted by most recent first.
    """
    limit = limit or config.MEMORY_TOP_K
    
    try:
        conn = sqlite3.connect(config.SESSION_DB_PATH)
        cursor = conn.cursor()
        
        # Extract key words from query for matching
        # Split into words, filter short words
        keywords = [w.lower() for w in query.split() if len(w) > 3]
        
        if not keywords:
            return []
        
        # Build a LIKE query for each keyword
        # This finds sessions whose query contains any of the keywords
        like_clauses = " OR ".join(["LOWER(query) LIKE ?" for _ in keywords])
        params       = [f"%{kw}%" for kw in keywords]
        
        cursor.execute(f"""
            SELECT session_id, query, focus_area, summary,
                   confidence_score, created_at
            FROM sessions
            WHERE ({like_clauses})
            ORDER BY created_at DESC
            LIMIT ?
        """, params + [limit])
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert rows to list of dicts
        sessions = []
        for row in rows:
            sessions.append({
                "session_id":       row[0],
                "query":            row[1],
                "focus_area":       row[2],
                "summary":          row[3],
                "confidence_score": row[4],
                "created_at":       row[5]
            })

        return sessions

    except Exception as e:
        print(f"⚠️  Failed to load sessions: {e}")
        return []
    
def summarize_prior_context(current_query: str, past_sessions: List[Dict[str, Any]]) -> str:
    """
    Use the LLM to summarize relevant past sessions into
    a short context string for injection into the Summarizer.

    Args:
        current_query: The new research question.
        past_sessions: List of relevant past session dicts.

    Returns:
        Short context summary string (max 300 tokens).
    """
    if not past_sessions:
        return "No relevant prior research found."
    
    # Format past sessions for the prompt
    sessions_text = ""
    for i, session in enumerate(past_sessions, 1):
        sessions_text += (
            f"\n[Session {i}] Query: {session['query']}\n"
            f"Date: {session['created_at'][:10]}\n"
            f"Summary: {session['summary'][:500]}\n"
        )
        
        # Ask LLM to extract only the relevant parts
        prompt = MEMORY_SUMMARIZER_PROMPT.format(
            new_query=current_query,
            previous_sessions=sessions_text
        )
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            print(f"⚠️  Context summarization failed: {e}")
            return "No relevant prior research found."


# ── Pre-Phase 1: Load Context ─────────────────────────────────


def run_memory_load(state: ResearchState) -> ResearchState:
    """
    Memory Agent — Load operation (runs before Phase 1).

    Reads from state:  query, session_id
    Writes to state:   chat_history, context_summary

    Args:
        state: Current ResearchState.

    Returns:
        Updated state with chat_history and context_summary.
    """
    print("🧠 Memory Agent — Loading prior context...")

    query = state["query"]

    # Initialize database on first run
    init_database()
    
def run_memory_load(state: ResearchState) -> ResearchState:
    """
    Memory Agent — Load operation (runs before Phase 1).

    Reads from state:  query, session_id
    Writes to state:   chat_history, context_summary

    Args:
        state: Current ResearchState.

    Returns:
        Updated state with chat_history and context_summary.
    """
    print("🧠 Memory Agent — Loading prior context...")

    query = state["query"]

    # Initialize database on first run
    init_database()
    
    # Load similar past sessions
    past_sessions = load_similar_sessions(query)
    print(f"   Found {len(past_sessions)} relevant past sessions")

    if past_sessions:
        # Summarize relevant context for injection
        context_summary = summarize_prior_context(query, past_sessions)
        print(f"   ✅ Context summary ready ({len(context_summary)} chars)")
    else:
        context_summary = "No relevant prior research found."
        print("   No prior context found — starting fresh")

    return {
        **state,
        "chat_history":    past_sessions,
        "context_summary": context_summary
    }
    
# ── Post-Report: Save Session ──────────────────────────────────

def run_memory_save(state: ResearchState) -> ResearchState:
    """
    Memory Agent — Save operation (runs after Report Agent).

    Reads from state:  all completed research fields
    Writes to state:   session_saved

    Args:
        state: Current ResearchState with completed research.

    Returns:
        Updated state with session_saved = True.
    """
    print("🧠 Memory Agent — Saving session...")

    success = save_session(state)

    if success:
        print(f"   ✅ Session saved: {state.get('session_id', '')[:8]}...")
    else:
        print("   ⚠️  Session save failed")

    return {
        **state,
        "session_saved": success
    }