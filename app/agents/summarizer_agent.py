# ============================================================
# app/agents/summarizer_agent.py
# ============================================================
# Summarizer Agent — Phase 2 (Sequential, Step 1)
#
# Takes outputs from all 3 parallel agents and merges them
# into a single coherent medical research summary.
#
# Flow:
#   1. Read search_results, rag_results, news_results from state
#   2. Format all results into a combined context
#   3. Use LLM to synthesize into one structured summary
#   4. Write summary back to state
# ============================================================

from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.utils.config import config
from app.utils.prompts import SUMMARIZER_AGENT_PROMPT
from app.utils.langsmith_config import trace_agent
from app.graph.state import ResearchState


# ── LLM Setup ─────────────────────────────────────────────────
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=config.GROQ_TEMPERATURE,
    max_tokens=config.GROQ_MAX_TOKENS
)


def format_search_results(results: List[Dict[str, Any]]) -> str:
    """
    Format search results into a readable string for the prompt.

    Args:
        results: List of {title, url, snippet} dicts.

    Returns:
        Formatted string with numbered results.
    """
    if not results:
        return "No web search results available."

    formatted = ""
    for i, r in enumerate(results[:5], 1):
        # Only use top 5 to keep prompt size manageable
        formatted += (
            f"\n[{i}] {r.get('title', 'No title')}\n"
            f"    URL: {r.get('url', '')}\n"
            f"    {r.get('snippet', '')}\n"
        )
    return formatted

def format_rag_results(results: List[Dict[str, Any]]) -> str:
    """
    Format RAG results into a readable string for the prompt.

    Args:
        results: List of {text, source, score, label} dicts.

    Returns:
        Formatted string with source references.
    """
    if not results:
        return "No knowledge base results available."
    
    formatted = ""
    for i, r in enumerate(results[:5], 1):
        # Only use top 5 validated chunks
        formatted += (
            f"\n[{i}] Source: {r.get('source', 'unknown')} "
            f"(score: {r.get('score', 0)})\n"
            f"    {r.get('text', '')[:500]}\n"  # Truncate long chunks
        )
    return formatted

def format_news_results(results: List[Dict[str, Any]]) -> str:
    """
    Format news results into a readable string for the prompt.

    Args:
        results: List of {title, url, date, source, summary} dicts.

    Returns:
        Formatted string with dates and sources.
    """
    if not results:
        return "No recent news available."

    formatted = ""
    for i, r in enumerate(results[:5], 1):
        formatted += (
            f"\n[{i}] {r.get('title', 'No title')}\n"
            f"    Source: {r.get('source', '')} | "
            f"Date: {r.get('date', '')}\n"
            f"    {r.get('summary', '')[:300]}\n"
        )
    return formatted

def run_summarizer_agent(state: ResearchState) -> ResearchState:
    """
    Main Summarizer Agent — called by LangGraph as a node.

    Reads from state:  search_results, rag_results, news_results,
                       query, focus_area, context_summary
    Writes to state:   summary

    Args:
        state: Current ResearchState from LangGraph.

    Returns:
        Updated state with summary filled in.
    """
    print("📝 Summarizer Agent running...")

    query = state["query"]
    focus_area = state.get("focus_area", "general")
    
    try:
        # Step 1: Format all parallel agent outputs
        search_text = format_search_results(state.get("search_results", []))
        rag_text = format_rag_results(state.get("rag_results", []))
        news_text = format_news_results(state.get("news_results", []))
         
        # Step 2: Get prior session context from Memory Agent
        # Empty string if Memory Agent hasn't run yet
        context_summary = state.get("context_summary", "No prior research context.")
        print("   Synthesizing all sources...")

        # Step 3: Fill in the summarizer prompt with all sources
        prompt = SUMMARIZER_AGENT_PROMPT.format(
            query=query,
            focus_area=focus_area,
            context_summary=context_summary,
            search_results=search_text,
            rag_results=rag_text,
            news_results=news_text
        )
        
        # Step 4: Ask LLM to synthesize everything into one summary
        response = llm.invoke([HumanMessage(content=prompt)])
        summary  = response.content

        print(f"   ✅ Summary generated ({len(summary)} characters)")

        return {
            **state,
            "summary": summary
        }

    except Exception as e:
        print(f"❌ Summarizer Agent failed: {e}")
        return {
            **state,
            "summary": "",
            "error":   f"Summarizer Agent error: {str(e)}"
        }