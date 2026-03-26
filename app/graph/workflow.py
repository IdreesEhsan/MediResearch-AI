from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import uuid
from typing import Optional
from app.graph.state import ResearchState, initial_state

from app.agents.memory_agent import run_memory_load, run_memory_save
from app.agents.search_agent import run_search_agent
from app.agents.rag_agent import run_rag_agent
from app.agents.news_agent import run_news_agent
from app.agents.summarizer_agent import run_summarizer_agent
from app.agents.factcheck_agent import run_factcheck_agent
from app.agents.report_agent import run_report_agent
from app.agents.export_agent import run_export_agent


def build_workflow():
    graph = StateGraph(ResearchState)

    # Add all nodes
    graph.add_node("memory_load",      run_memory_load)
    graph.add_node("search_agent",     run_search_agent)
    graph.add_node("rag_agent",        run_rag_agent)
    graph.add_node("news_agent",       run_news_agent)
    graph.add_node("summarizer_agent", run_summarizer_agent)
    graph.add_node("factcheck_agent",  run_factcheck_agent)
    graph.add_node("report_agent",     run_report_agent)
    graph.add_node("export_agent",     run_export_agent)
    graph.add_node("memory_save",      run_memory_save)

    # Entry point
    graph.set_entry_point("memory_load")

    # Parallel Phase 1
    graph.add_edge("memory_load", "search_agent")
    graph.add_edge("memory_load", "rag_agent")
    graph.add_edge("memory_load", "news_agent")

    # Fan-in to summarizer
    graph.add_edge("search_agent", "summarizer_agent")
    graph.add_edge("rag_agent", "summarizer_agent")
    graph.add_edge("news_agent", "summarizer_agent")

    # Sequential chain (HITL completely removed)
    graph.add_edge("summarizer_agent", "factcheck_agent")
    graph.add_edge("factcheck_agent",  "report_agent")
    graph.add_edge("report_agent",     "export_agent")
    graph.add_edge("export_agent",     "memory_save")
    graph.add_edge("memory_save",      END)

    app = graph.compile(checkpointer=MemorySaver())
    print("✅ LangGraph workflow compiled successfully (HITL removed)")
    return app


def run_research(
    query: str,
    focus_area: str = "general",
    session_id: Optional[str] = None
) -> ResearchState:
    session_id = session_id or str(uuid.uuid4())
    
    state = initial_state(query, focus_area, session_id)

    app = build_workflow()
    config_dict = {"configurable": {"thread_id": session_id}}

    print(f"\n{'='*60}")
    print(f"🏥 Starting MediResearch AI Session: {session_id[:8]}...")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    result = app.invoke(state, config=config_dict)

    print(f"\n{'='*60}")
    print(f"✅ Research completed!")
    print(f"   Confidence    : {result.get('confidence_score', 0)}/100")
    print(f"   Report length : {len(result.get('final_report', ''))} characters")
    print(f"{'='*60}\n")

    return result