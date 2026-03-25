# ============================================================
# app/graph/workflow.py
# ============================================================
# LangGraph StateGraph — connects all 8 agents into one
# unified research pipeline.
#
# HITL is handled by checking hitl_decision inside the node
# instead of using interrupt_before — this is more reliable
# for testing and works the same way in production.
# ============================================================
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import ResearchState, HITLDecision, initial_state
from app.graph.router import after_hitl_router

from app.agents.memory_agent import run_memory_load, run_memory_save
from app.agents.search_agent import run_search_agent
from app.agents.rag_agent import run_rag_agent
from app.agents.news_agent import run_news_agent
from app.agents.summarizer_agent import run_summarizer_agent
from app.agents.factcheck_agent import run_factcheck_agent
from app.agents.report_agent import run_report_agent
from app.agents.export_agent import run_export_agent
import uuid
from typing import Optional

def hitl_node(state: ResearchState) -> ResearchState:
    decision = state.get("hitl_decision", HITLDecision.PENDING)
    print(f"⏸️  HITL Node — Decision: {decision} | Session: {state.get('session_id', '')[:8]}...")
    return state


def increment_retry(state: ResearchState) -> ResearchState:
    current = state.get("retry_count", 0)
    print(f"   🔄 Retry count increased to {current + 1}/3")
    return {**state, "retry_count": current + 1}


def build_workflow():
    graph = StateGraph(ResearchState)

    graph.add_node("memory_load", run_memory_load)
    graph.add_node("search_agent", run_search_agent)
    graph.add_node("rag_agent", run_rag_agent)
    graph.add_node("news_agent", run_news_agent)
    graph.add_node("summarizer_agent", run_summarizer_agent)
    graph.add_node("factcheck_agent", run_factcheck_agent)
    graph.add_node("hitl_node", hitl_node)
    graph.add_node("retry_node", increment_retry)
    graph.add_node("report_agent", run_report_agent)
    graph.add_node("export_agent", run_export_agent)
    graph.add_node("memory_save", run_memory_save)

    graph.set_entry_point("memory_load")

    # Parallel Phase 1
    graph.add_edge("memory_load", "search_agent")
    graph.add_edge("memory_load", "rag_agent")
    graph.add_edge("memory_load", "news_agent")

    # Fan-in
    graph.add_edge("search_agent", "summarizer_agent")
    graph.add_edge("rag_agent", "summarizer_agent")
    graph.add_edge("news_agent", "summarizer_agent")

    # Sequential
    graph.add_edge("summarizer_agent", "factcheck_agent")
    graph.add_edge("factcheck_agent", "hitl_node")

    # Conditional routing (now correct)
    graph.add_conditional_edges(
        "hitl_node",
        after_hitl_router,
        {
            "report_agent": "report_agent",
            "retry_node": "retry_node",
            "hitl_node": "hitl_node",
        }
    )

    graph.add_edge("retry_node", "summarizer_agent")

    # Happy path
    graph.add_edge("report_agent", "export_agent")
    graph.add_edge("export_agent", "memory_save")
    graph.add_edge("memory_save", END)

    app = graph.compile(checkpointer=MemorySaver())
    print("✅ LangGraph workflow compiled successfully")
    return app


def run_research(
    query: str,
    focus_area: str = "general",
    session_id: Optional[str] = None,
    auto_approve: bool = False
) -> ResearchState:
    session_id = session_id or str(uuid.uuid4())
    state = initial_state(query, focus_area, session_id)

    if auto_approve:
        state["hitl_decision"] = HITLDecision.APPROVED
        state["hitl_comments"] = "Auto-approved for testing"

    app = build_workflow()
    config_dict = {"configurable": {"thread_id": session_id}}

    print(f"\n{'='*60}\nStarting MediResearch AI Session: {session_id[:8]}...\n{'='*60}")
    result = app.invoke(state, config=config_dict)
    print(f"✅ Research completed! Confidence: {result.get('confidence_score', 0)}/100\n{'='*60}\n")

    return result