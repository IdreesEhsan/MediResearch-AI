# ============================================================
# app/agents/search_agent.py
# ============================================================
# Search Agent — Phase 1 (Parallel)
#
# Searches the web using DuckDuckGo (free, no API key needed)
# or SerpAPI (optional, better results).
#
# Flow:
#   1. Generate targeted search queries using the LLM
#   2. Search the web for each query
#   3. Return results as a list of {title, url, snippet}
# ============================================================

import json
import time
from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from duckduckgo_search import DDGS

from app.utils.config import config
from app.utils.prompts import SEARCH_AGENT_PROMPT
from app.utils.langsmith_config import trace_agent
from app.graph.state import ResearchState


# ── LLM Setup ─────────────────────────────────────────────────
# Initialize Groq LLM — shared across all agents
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=config.GROQ_TEMPERATURE,
    max_tokens=config.GROQ_MAX_TOKENS
)

def generate_search_queries(query: str, focus_area: str) -> List[str]:
    """
    Use the LLM to generate 3-5 targeted search queries.

    Instead of searching with the raw user question, we ask the
    LLM to generate better, more specific medical search queries.
    This improves the quality of search results significantly.

    Args:
        query:      The user's research question.
        focus_area: Research domain (general/disease/drug/news).

    Returns:
        List of optimized search query strings.
    """
    prompt = SEARCH_AGENT_PROMPT.format(
        query=query,
        focus_area=focus_area
    )
    
    # Ask the LLM to generate better search queries
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        # LLM returns a JSON list — parse it
        queries = json.loads(response.content)
        if isinstance(queries, list):
            return queries[:5] # Max 5 queries
    except json.JSONDecodeError:
        # If LLM doesn't return valid JSON, fall back to original query
        pass
    
    # Fallback — use the original query directly
    return [query]


def search_web(queries: List[str], max_results: int = None) -> List[Dict[str, Any]]:
    """
    Execute web searches using DuckDuckGo with retry logic.
    Includes delays to avoid rate limiting.
    """
    import time
    max_results = max_results or config.SEARCH_MAX_RESULTS
    all_results = []
    seen_urls   = set()

    for query in queries:
        # Wait 5 seconds between each query to avoid rate limiting
        time.sleep(5)
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    backend="lite"   # Use lite backend — less likely to be rate limited
                ))

                for r in results:
                    url = r.get("href", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    all_results.append({
                        "title":   r.get("title", ""),
                        "url":     url,
                        "snippet": r.get("body", ""),
                        "query":   query
                    })

        except Exception as e:
            print(f"⚠️  Search failed for '{query}': {e}")
            continue

    return all_results

@trace_agent("search_agent")
def run_search_agent(state: ResearchState) -> ResearchState:
    """
    Main Search Agent function — called by LangGraph as a node.

    Reads from state:  query, focus_area
    Writes to state:   search_results, sources

    Args:
        state: Current ResearchState from LangGraph.

    Returns:
        Updated state with search_results and sources filled in.
    """
    print("🔍 Search Agent running...")

    query = state['query']
    focus_area = state["focus_area"]
    
    try:
        # Step 1: Generate targeted search queries using LLM
        print("   Generating search queries...")
        queries = generate_search_queries(query, focus_area)
        print(f"   Generated {len(queries)} queries")

        # Step 2: Search the web for each query
        print("   Searching the web...")
        results = search_web(queries)
        print(f"   Found {len(results)} results")

        # Step 3: Extract source URLs for the bibliography
        sources = [r["url"] for r in results if r.get("url")]

        return {
            **state,
            "search_results": results,
            "sources":        list(set(state.get("sources", []) + sources))
        }

    except Exception as e:
        # If search fails, return error in state but don't crash workflow
        print(f"❌ Search Agent failed: {e}")
        return {
            **state,
            "search_results": [],
            "error":          f"Search Agent error: {str(e)}"
        }