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
from app.utils.langsmith_config import trace_agent

llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=0.0,
    max_tokens=500
)

def init_database() -> None:
    conn = sqlite3.connect(config.SESSION_DB_PATH)
    cursor = conn.cursor()
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exports (
            export_id   TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            format      TEXT NOT NULL,
            file_path   TEXT,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def save_session(state: ResearchState) -> bool:
    try:
        conn = sqlite3.connect(config.SESSION_DB_PATH)
        cursor = conn.cursor()
        
        sources_json = json.dumps(state.get('sources', []))
        
        # Clean status - no more HITL dependency
        confidence = state.get("confidence_score", 0)
        status = "Completed" if confidence >= 60 else "Low Confidence"

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
            confidence,
            1,  # We treat all as approved since HITL is removed
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Session saved: {state.get('session_id', '')[:8]} | Confidence: {confidence}/100 | Status: Completed")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save session: {e}")
        return False

def load_similar_sessions(query: str, limit: int = None) -> List[Dict[str, Any]]:
    limit = limit or config.MEMORY_TOP_K
    try:
        conn = sqlite3.connect(config.SESSION_DB_PATH)
        cursor = conn.cursor()
        
        keywords = [w.lower() for w in query.split() if len(w) > 3]
        if not keywords:
            return []
        
        like_clauses = " OR ".join(["LOWER(query) LIKE ?" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        
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
        
        return [{
            "session_id": row[0],
            "query": row[1],
            "focus_area": row[2],
            "summary": row[3],
            "confidence_score": row[4],
            "created_at": row[5]
        } for row in rows]

    except Exception as e:
        print(f"⚠️ Failed to load sessions: {e}")
        return []

def summarize_prior_context(current_query: str, past_sessions: List[Dict[str, Any]]) -> str:
    if not past_sessions:
        return "No relevant prior research found."
    
    sessions_text = ""
    for i, session in enumerate(past_sessions, 1):
        sessions_text += f"\n[Session {i}] Query: {session['query']}\nDate: {session['created_at'][:10]}\nSummary: {session['summary'][:500]}\n"
    
    prompt = MEMORY_SUMMARIZER_PROMPT.format(
        new_query=current_query,
        previous_sessions=sessions_text
    )
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        print(f"⚠️ Context summarization failed: {e}")
        return "No relevant prior research found."

# ── Public Functions used by workflow ────────────────────────

@trace_agent("memory_load")
def run_memory_load(state: ResearchState) -> ResearchState:
    print("🧠 Memory Agent — Loading prior context...")
    query = state["query"]
    init_database()
    
    past_sessions = load_similar_sessions(query)
    print(f"   Found {len(past_sessions)} relevant past sessions")
    
    context_summary = summarize_prior_context(query, past_sessions) if past_sessions else "No relevant prior research found."
    
    return {
        **state,
        "chat_history": past_sessions,
        "context_summary": context_summary
    }

@trace_agent("memory_save")
def run_memory_save(state: ResearchState) -> ResearchState:
    print("🧠 Memory Agent — Saving session...")
    success = save_session(state)
    print(f"   {'✅ Session saved' if success else '⚠️ Session save failed'}")
    return {**state, "session_saved": success}