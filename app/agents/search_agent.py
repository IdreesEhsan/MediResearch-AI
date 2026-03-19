# ============================================================
# app/agents/search_agent.py
# ============================================================
# Search Agent — Phase 1 (Parallel)
#
# Uses Tavily Search API — designed specifically for AI agents.
# No rate limiting, high quality results, free tier available.
#
# Fallback: DuckDuckGo if Tavily key is not set
# ============================================================

import time
from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.utils.config import config
from app.graph.state import ResearchState


# ── LLM Setup ─────────────────────────────────────────────────
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=config.GROQ_TEMPERATURE,
    max_tokens=config.GROQ_MAX_TOKENS
)


def generate_search_queries(query: str, focus_area: str) -> List[str]:
    """
    Generate simple focused search queries based on focus area.

    Args:
        query:      The user's research question.
        focus_area: Research domain.

    Returns:
        List of 3 simple search query strings.
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
        return [
            f"{clean_query} medical overview",
            f"{clean_query} treatment guidelines",
            f"{clean_query} research findings"
        ]


def search_with_tavily(queries: List[str]) -> List[Dict[str, Any]]:
    """
    Search using Tavily API — best option for AI agents.
    No rate limiting, high quality medical results.

    Args:
        queries: List of search query strings.

    Returns:
        List of {title, url, snippet} dicts.
    """
    try:
        from tavily import TavilyClient
    except ModuleNotFoundError:
        print("⚠️  Tavily client package is not installed. Falling back to DuckDuckGo.")
        print("   Install with: pip install tavily")
        return search_with_duckduckgo(queries)

    client      = TavilyClient(api_key=config.TAVILY_API_KEY)
    all_results = []
    seen_urls   = set()

    for query in queries:
        try:
            # Tavily search — returns clean, relevant results
            response = client.search(
                query=query,
                max_results=config.SEARCH_MAX_RESULTS,
                search_depth="basic"  # "basic" is free, "advanced" is paid
            )

            for r in response.get("results", []):
                url = r.get("url", "")

                # Skip duplicates
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


def search_with_duckduckgo(queries: List[str]) -> List[Dict[str, Any]]:
    """
    Fallback search using DuckDuckGo.
    Used only if Tavily API key is not set.

    Args:
        queries: List of search query strings.

    Returns:
        List of {title, url, snippet} dicts.
    """
    from duckduckgo_search import DDGS

    all_results = []
    seen_urls   = set()

    for query in queries:
        # Wait between requests to avoid rate limiting
        time.sleep(8)

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=config.SEARCH_MAX_RESULTS,
                    backend="lite"
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
            print(f"⚠️  DuckDuckGo failed for '{query}': {e}")
            continue

    return all_results


def search_web(queries: List[str]) -> List[Dict[str, Any]]:
    """
    Main search function — uses Tavily if key is set,
    falls back to DuckDuckGo otherwise.

    Args:
        queries: List of search query strings.

    Returns:
        List of {title, url, snippet} dicts.
    """
    if config.TAVILY_API_KEY:
        print("   Using Tavily Search...")
        return search_with_tavily(queries)
    else:
        print("   Using DuckDuckGo (fallback)...")
        return search_with_duckduckgo(queries)


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
        # Step 1: Generate targeted queries
        queries = generate_search_queries(query, focus_area)
        print(f"   Generated {len(queries)} queries")

        # Step 2: Search the web
        results = search_web(queries)
        print(f"   Found {len(results)} results")

        # Step 3: Extract source URLs
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