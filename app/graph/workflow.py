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

from app.graph.state import ResearchState, HITLDecision
from app.graph.router import after_hitl_router
from app.utils.langsmith_config import setup_langsmith

# ── Import all agents ─────────────────────────────────────────
from app.agents.memory_agent import run_memory_load, run_memory_save
from app.agents.search_agent import run_search_agent
from app.agents.rag_agent import run_rag_agent
from app.agents.news_agent import run_news_agent
from app.agents.summarizer_agent import run_summarizer_agent
from app.agents.factcheck_agent import run_factcheck_agent
from app.agents.report_agent import run_report_agent
from app.agents.export_agent import run_export_agent


# ── HITL Node ─────────────────────────────────────────────────

def hitl_node(state: ResearchState) -> ResearchState:
    """
    Human-in-the-Loop node.

    In test mode (auto_approve=True) hitl_decision is already
    set to APPROVED before the workflow reaches this node so
    it passes through immediately.

    In production the FastAPI endpoint sets hitl_decision
    externally before resuming the workflow.
    """
    decision = state.get("hitl_decision", HITLDecision.PENDING)
    print(f"⏸️  HITL Node — Decision: {decision}")
    print(f"   Session    : {state.get('session_id', '')[:8]}...")
    print(f"   Confidence : {state.get('confidence_score', 0)}/100")
    return state


def increment_retry(state: ResearchState) -> ResearchState:
    """Increment retry counter when doctor rejects."""
    current = state.get("retry_count", 0)
    print(f"   🔄 Retry {current + 1}/3")
    return {"retry_count": current + 1}


# ── Build the Graph ───────────────────────────────────────────

def build_workflow():
    """
    Build and compile the LangGraph StateGraph.
    """
    setup_langsmith()

    graph = StateGraph(ResearchState)

    # ── Add nodes ─────────────────────────────────────────────
    graph.add_node("memory_load",      run_memory_load)
    graph.add_node("search_agent",     run_search_agent)
    graph.add_node("rag_agent",        run_rag_agent)
    graph.add_node("news_agent",       run_news_agent)
    graph.add_node("summarizer_agent", run_summarizer_agent)
    graph.add_node("factcheck_agent",  run_factcheck_agent)
    graph.add_node("hitl_node",        hitl_node)
    graph.add_node("retry_node",       increment_retry)
    graph.add_node("report_agent",     run_report_agent)
    graph.add_node("export_agent",     run_export_agent)
    graph.add_node("memory_save",      run_memory_save)

    # ── Entry point ───────────────────────────────────────────
    graph.set_entry_point("memory_load")

    # ── Edges ─────────────────────────────────────────────────
    # memory_load → 3 parallel agents
    graph.add_edge("memory_load",  "search_agent")
    graph.add_edge("memory_load",  "rag_agent")
    graph.add_edge("memory_load",  "news_agent")

    # 3 parallel → summarizer (fan-in)
    graph.add_edge("search_agent", "summarizer_agent")
    graph.add_edge("rag_agent",    "summarizer_agent")
    graph.add_edge("news_agent",   "summarizer_agent")

    # Sequential chain
    graph.add_edge("summarizer_agent", "factcheck_agent")
    graph.add_edge("factcheck_agent",  "hitl_node")

    # HITL → conditional routing
    graph.add_conditional_edges(
        "hitl_node",
        after_hitl_router,
        {
            "report_agent":     "report_agent",
            "summarizer_agent": "retry_node",
            "hitl_node":        "hitl_node",
        }
    )

    # Retry loop
    graph.add_edge("retry_node", "summarizer_agent")

    # Happy path
    graph.add_edge("report_agent", "export_agent")
    graph.add_edge("export_agent", "memory_save")
    graph.add_edge("memory_save",  END)

    # Compile without interrupt_before
    app = graph.compile(checkpointer=MemorySaver())
    print("✅ LangGraph workflow compiled successfully")
    return app


# ── Run research ──────────────────────────────────────────────

def run_research(
    query: str,
    focus_area: str = "general",
    session_id: str = None,
    auto_approve: bool = False
) -> ResearchState:
    """
    Run a complete research session.

    For auto_approve=True the hitl_decision is set to APPROVED
    in the initial state so the workflow passes through HITL
    without pausing.
    """
    import uuid
    from app.graph.state import initial_state

    session_id = session_id or str(uuid.uuid4())

    # Create initial state
    state = initial_state(query, focus_area, session_id)

    # If auto_approve set decision before workflow starts
    # so HITL node sees APPROVED and routes to report_agent
    if auto_approve:
        state["hitl_decision"] = HITLDecision.APPROVED
        state["hitl_comments"] = "Auto-approved for testing"
        print("🤖 Auto-approve enabled")

    app = build_workflow()
    config_dict = {"configurable": {"thread_id": session_id}}

    print(f"\n{'='*55}")
    print(f"🏥 MediResearch AI — Starting Research")
    print(f"{'='*55}")
    print(f"Query      : {query}")
    print(f"Focus Area : {focus_area}")
    print(f"Session ID : {session_id[:8]}...")
    print(f"{'='*55}\n")

    # Single invoke — runs entire workflow end to end
    result = app.invoke(state, config=config_dict)

    print(f"\n{'='*55}")
    print(f"✅ Research complete!")
    print(f"   Confidence    : {result.get('confidence_score', 0)}/100")
    print(f"   Report length : {len(result.get('final_report', ''))} chars")
    print(f"   PDF           : {result.get('export_pdf_path', 'N/A')}")
    print(f"   Word          : {result.get('export_word_path', 'N/A')}")
    print(f"{'='*55}\n")

    return result