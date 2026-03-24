# ============================================================
# app/agents/search_agent.py
# ============================================================
# Search Agent — Phase 1 (Parallel)
#
# Uses Tavily Search API exclusively.
# Tavily is designed for AI agents — no rate limiting,
# high quality results, free tier: 1000 searches/month.
#
# Get your key at: https://tavily.com
# ============================================================

from typing import List, Dict, Any
from tavily import TavilyClient

from langchain_groq import ChatGroq
from app.utils.config import config
from app.utils.langsmith_config import trace_agent
from app.graph.state import ResearchState


# ── LLM Setup ─────────────────────────────────────────────────
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=config.GROQ_TEMPERATURE,
    max_tokens=config.GROQ_MAX_TOKENS
)

# ── Tavily Client ─────────────────────────────────────────────
# Initialize once — reused for all searches
tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)


def generate_search_queries(query: str, focus_area: str) -> List[str]:
    """
    Generate 3 focused search queries based on focus area.
    Simple direct queries work best with Tavily.

    Args:
        query:      The user's research question.
        focus_area: Research domain.

    Returns:
        List of 3 search query strings.
    """
    clean_query = query.strip()

    if focus_area == "disease":
        return [
            f"{clean_query} symptoms causes",
            f"{clean_query} treatment options",
            f"{clean_query} latest research"
        ]
    elif focus_area == "drug":
        return [
            f"{clean_query} dosage side effects",
            f"{clean_query} uses indications",
            f"{clean_query} clinical trials"
        ]
    elif focus_area == "news":
        return [
            f"{clean_query} latest news 2024",
            f"{clean_query} recent developments",
            f"{clean_query} new findings"
        ]
    else:
        # General medical queries
        return [
            f"{clean_query} medical overview",
            f"{clean_query} treatment guidelines",
            f"{clean_query} research findings"
        ]


def search_with_tavily(queries: List[str]) -> List[Dict[str, Any]]:
    """
    Execute web searches using Tavily API.

    Tavily is purpose-built for AI agents:
    - No rate limiting
    - Returns clean, relevant content
    - Filters out low quality pages automatically
    - Free tier: 1000 searches/month

    Args:
        queries: List of search query strings.

    Returns:
        List of {title, url, snippet, query} dicts.
    """
    all_results = []
    seen_urls   = set()  # Track URLs to avoid duplicates

    for query in queries:
        try:
            # Search using Tavily
            # search_depth="basic" uses free tier credits
            # search_depth="advanced" gives better results (costs more credits)
            response = tavily_client.search(
                query        = query,
                max_results  = config.SEARCH_MAX_RESULTS,
                search_depth = "basic"
            )

            for r in response.get("results", []):
                url = r.get("url", "")

                # Skip duplicate URLs
                if url in seen_urls:
                    continue

                seen_urls.add(url)
                all_results.append({
                    "title":   r.get("title", ""),
                    "url":     url,
                    "snippet": r.get("content", ""),
                    "query":   query
                })

        except Exception as e:
            print(f"⚠️  Tavily search failed for '{query}': {e}")
            continue

    return all_results


@trace_agent("search_agent")
def run_search_agent(state: ResearchState) -> ResearchState:
    """
    Main Search Agent — called by LangGraph as a node.

    Reads from state:  query, focus_area
    Writes to state:   search_results, sources

    Args:
        state: Current ResearchState from LangGraph.

    Returns:
        Updated state with search_results and sources.
    """
    print("🔍 Search Agent running...")

    query      = state["query"]
    focus_area = state.get("focus_area", "general")

    try:
        # Step 1: Generate targeted search queries
        queries = generate_search_queries(query, focus_area)
        print(f"   Generated {len(queries)} queries")

        # Step 2: Search using Tavily
        print("   Searching with Tavily...")
        results = search_with_tavily(queries)
        print(f"   ✅ Found {len(results)} results")

        # Step 3: Extract source URLs for bibliography
        sources = [r["url"] for r in results if r.get("url")]

        return {
            "search_results": results,
            "sources":        sources
        }

    except Exception as e:
        print(f"❌ Search Agent failed: {e}")
        return {
            "search_results": [],
            "sources":        []
        }