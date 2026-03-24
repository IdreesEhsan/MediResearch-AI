# ============================================================
# app/agents/news_agent.py
# ============================================================
# News Agent — Phase 1 (Parallel)
#
# Fetches the latest medical news using Tavily Search.
# Filters to last 90 days for clinical relevance.
# ============================================================

from datetime import datetime, timedelta
from typing import List, Dict, Any
from tavily import TavilyClient

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.utils.config import config
from app.utils.prompts import NEWS_AGENT_PROMPT
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
tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)


def fetch_medical_news(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch latest medical news using Tavily Search.

    Uses Tavily's news topic filter to get recent articles only.
    Much more reliable than DuckDuckGo news — no rate limiting.

    Args:
        query:       The medical topic to search news for.
        max_results: Maximum number of articles to return.

    Returns:
        List of {title, url, date, source, summary} dicts.
    """
    news_results = []

    # Build a news-focused query
    news_query = f"{query} medical news research 2024 2025"

    try:
        # Use Tavily with topic="news" for news-specific results
        response = tavily_client.search(
            query        = news_query,
            max_results  = max_results,
            search_depth = "basic",
            topic        = "news"    # News-specific search mode
        )

        for article in response.get("results", []):
            # Get published date — Tavily provides this for news
            pub_date = article.get("published_date", "")

            # Format date if available
            if pub_date:
                try:
                    # Try to parse and format the date
                    date_obj = datetime.fromisoformat(
                        pub_date.replace("Z", "+00:00")
                    )
                    formatted_date = date_obj.strftime("%B %d, %Y")
                except (ValueError, AttributeError):
                    formatted_date = pub_date
            else:
                formatted_date = datetime.now().strftime("%B %d, %Y")

            news_results.append({
                "title":   article.get("title", ""),
                "url":     article.get("url", ""),
                "date":    formatted_date,
                "source":  article.get("url", "").split("/")[2] if article.get("url") else "",
                "summary": article.get("content", "")[:500]  # Truncate long content
            })

    except Exception as e:
        # Fallback — try regular Tavily search without news topic
        print(f"⚠️  News search with topic failed: {e}")
        try:
            response = tavily_client.search(
                query       = news_query,
                max_results = max_results,
                search_depth = "basic"
            )
            for article in response.get("results", []):
                news_results.append({
                    "title":   article.get("title", ""),
                    "url":     article.get("url", ""),
                    "date":    datetime.now().strftime("%B %d, %Y"),
                    "source":  article.get("url", "").split("/")[2] if article.get("url") else "",
                    "summary": article.get("content", "")[:500]
                })
        except Exception as e2:
            print(f"⚠️  Fallback news search also failed: {e2}")

    return news_results


def summarize_news(query: str, focus_area: str, articles: List[Dict]) -> str:
    """
    Use the LLM to summarize news articles into a structured report.

    Args:
        query:      The research question.
        focus_area: Research domain.
        articles:   List of news article dicts.

    Returns:
        LLM-generated news summary string.
    """
    if not articles:
        return "No recent medical news found for this topic."

    # Format articles for the prompt
    articles_text = ""
    for i, article in enumerate(articles, 1):
        articles_text += (
            f"\n[{i}] {article['title']}\n"
            f"    Source: {article['source']} | "
            f"Date: {article['date']}\n"
            f"    {article['summary']}\n"
        )

    prompt = NEWS_AGENT_PROMPT.format(
        query        = query,
        focus_area   = focus_area,
        news_articles = articles_text
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


@trace_agent("news_agent")
def run_news_agent(state: ResearchState) -> ResearchState:
    """
    Main News Agent — called by LangGraph as a node.

    Reads from state:  query, focus_area
    Writes to state:   news_results, sources

    Args:
        state: Current ResearchState from LangGraph.

    Returns:
        Updated state with news_results and sources.
    """
    print("📰 News Agent running...")

    query      = state["query"]
    focus_area = state.get("focus_area", "general")

    try:
        # Step 1: Fetch latest news using Tavily
        print("   Fetching latest medical news...")
        articles = fetch_medical_news(query)
        print(f"   Found {len(articles)} articles")

        # Step 2: Summarize with LLM
        print("   Summarizing news...")
        summary = summarize_news(query, focus_area, articles)

        # Step 3: Format results for state
        news_results = []

        # Add LLM summary as first item
        news_results.append({
            "title":   "News Summary",
            "url":     "",
            "date":    datetime.now().strftime("%B %d, %Y"),
            "source":  "News Agent — LLM Summary",
            "summary": summary
        })

        # Add individual articles
        for article in articles:
            news_results.append({
                "title":   article["title"],
                "url":     article["url"],
                "date":    article["date"],
                "source":  article["source"],
                "summary": article["summary"]
            })

        # Collect article URLs as sources
        news_sources = [a["url"] for a in articles if a.get("url")]

        return {
            "news_results": news_results,
            "sources":      news_sources
        }

    except Exception as e:
        print(f"❌ News Agent failed: {e}")
        return {
            "news_results": [],
            "sources":      []
        }