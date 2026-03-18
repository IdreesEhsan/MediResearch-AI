# ============================================================
# app/agents/news_agent.py
# ============================================================
# News Agent — Phase 1 (Parallel)
#
# Fetches the latest medical news related to the query.
# Only returns articles from the last 90 days to keep
# results current and clinically relevant.
#
# Flow:
#   1. Build news-specific search queries
#   2. Search DuckDuckGo News
#   3. Filter by date (last 90 days)
#   4. Summarize findings using the LLM
#   5. Return results to state
# ============================================================

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from duckduckgo_search import DDGS

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

def fetch_medical_news(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch latest medical news using DuckDuckGo News search.

    Uses the news-specific endpoint which returns articles
    with publication dates — unlike regular web search.

    Args:
        query:       The medical topic to search for.
        max_results: Maximum number of news articles to return.

    Returns:
        List of {title, url, date, source, summary} dicts.
    """
    news_results = []
    
    # Calculate the cutoff date — only news from last 90 days
    cutoff_date = datetime.now() - timedelta(days=config.NEWS_LOOKBACK_DAYS)
    
    # Build a news-focused query
    news_query = f"{query} medical research news"
    
    try:
         # Wait before searching to avoid rate limiting
        time.sleep(3)
        
        with DDGS() as ddgs:
            # Use news() instead of text() — returns articles with dates
            results = list(ddgs.news(
                news_query,
                max_results=max_results
            ))
            
            for article in results:
                # Parse the publication date
                pub_date_str = article.get("date", "")
                try:
                    # DuckDuckGo returns dates in various formats
                    pub_date = datetime.fromisoformat(
                        pub_date_str.replace("Z", "+00:00")
                    )
                    # Make it timezone-naive for comparison
                    pub_date = pub_date.replace(tzinfo=None)

                    # Skip articles older than 90 days
                    if pub_date < cutoff_date:
                        continue
                    
                    formatted_date = pub_date.strftime("%B %d, %Y")
                    
                except (ValueError, AttributeError):
                     # If date can't be parsed keep the article anyway
                     formatted_date = pub_date_str
                     
                news_results.append({
                    "title":   article.get("title", ""),
                    "url":     article.get("url", ""),
                    "date":    formatted_date,
                    "source":  article.get("source", ""),
                    "summary": article.get("body", "")
                })
    
    except Exception as e:
        print(f"⚠️  News search failed: {e}")

    return news_results

def summarize_news(query: str, focus_area: str, articles: List[Dict]) -> str:
    """
    Use the LLM to summarize the news articles into a structured report.

    Args:
        query:      The research question.
        focus_area: Research domain.
        articles:   List of news article dicts.

    Returns:
        LLM-generated news summary string.
    """
    if not articles:
        return "No recent medical news found for this topic."

    # Format articles into a readable string for the prompt
    articles_text = ""
    for i, article in enumerate(articles, 1):
        articles_text += (
            f"\n[{i}] {article['title']}\n"
            f"    Source: {article['source']} | Date: {article['date']}\n"
            f"    {article['summary']}\n"
        )

    # Fill in the news prompt template
    prompt = NEWS_AGENT_PROMPT.format(
        query=query,
        focus_area=focus_area,
        news_articles=articles_text
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

@trace_agent("news_agent")
def run_news_agent(state: ResearchState) -> ResearchState:
    """
    Main News Agent function — called by LangGraph as a node.

    Reads from state:  query, focus_area
    Writes to state:   news_results, sources

    Args:
        state: Current ResearchState from LangGraph.

    Returns:
        Updated state with news_results and sources filled in.
    """
    print("📰 News Agent running...")

    query      = state["query"]
    focus_area = state.get("focus_area", "general")
    
    try:
        # Step 1: Fetch latest news articles
        print("   Fetching latest medical news...")
        articles = fetch_medical_news(query)
        print(f"   Found {len(articles)} recent articles")

        # Step 2: Summarize using LLM
        print("   Summarizing news...")
        summary = summarize_news(query, focus_area, articles)

        # Step 3: Format results for state
        news_results = []
        for article in articles:
            news_results.append({
                "title":   article["title"],
                "url":     article["url"],
                "date":    article["date"],
                "source":  article["source"],
                "summary": article["summary"]
            })

        # Add LLM summary as first item
        news_results.insert(0, {
            "title":   "News Summary",
            "url":     "",
            "date":    datetime.now().strftime("%B %d, %Y"),
            "source":  "News Agent — LLM Summary",
            "summary": summary
        })

        # Collect article URLs as sources
        news_sources = [a["url"] for a in articles if a.get("url")]
        all_sources  = list(set(state.get("sources", []) + news_sources))

        return {
            **state,
            "news_results": news_results,
            "sources":      all_sources
        }

    except Exception as e:
        print(f"❌ News Agent failed: {e}")
        return {
            **state,
            "news_results": [],
            "error":        f"News Agent error: {str(e)}"
        }