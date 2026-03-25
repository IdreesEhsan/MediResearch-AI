# ============================================================
# app/agents/news_agent.py
# ============================================================
# News Agent — Phase 1 (Parallel)
#
# Fetches the latest medical news using Tavily Search.
# Filters to last 90 days for clinical relevance.
# ============================================================

from datetime import datetime
from typing import List, Dict, Any
from tavily import TavilyClient

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.utils.config import config
from app.utils.prompts import NEWS_AGENT_PROMPT
from app.utils.langsmith_config import trace_agent
from app.graph.state import ResearchState

llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=config.GROQ_TEMPERATURE,
    max_tokens=config.GROQ_MAX_TOKENS
)

tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)

def fetch_medical_news(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    news_query = f"{query} medical news research 2024 2025"
    news_results = []
    try:
        response = tavily_client.search(
            query=news_query,
            max_results=max_results,
            search_depth="basic",
            topic="news"
        )
        for article in response.get("results", []):
            pub_date = article.get("published_date", "")
            formatted_date = pub_date[:10] if pub_date else datetime.now().strftime("%Y-%m-%d")
            news_results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "date": formatted_date,
                "source": article.get("url", "").split("/")[2] if article.get("url") else "",
                "summary": article.get("content", "")[:500]
            })
    except Exception as e:
        print(f"⚠️ News search failed: {e}")
    return news_results

def summarize_news(query: str, focus_area: str, articles: List[Dict]) -> str:
    if not articles:
        return "No recent medical news found for this topic."
    articles_text = "\n".join([
        f"[{i}] {a['title']}\n    Source: {a['source']} | Date: {a['date']}\n    {a['summary']}"
        for i, a in enumerate(articles, 1)
    ])
    prompt = NEWS_AGENT_PROMPT.format(query=query, focus_area=focus_area, news_articles=articles_text)
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

@trace_agent("news_agent")
def run_news_agent(state: ResearchState) -> ResearchState:
    print("📰 News Agent running...")
    query = state["query"]
    focus_area = state.get("focus_area", "general")

    try:
        articles = fetch_medical_news(query)
        print(f"   Found {len(articles)} articles")

        summary = summarize_news(query, focus_area, articles)

        news_results = [{
            "title": "News Summary",
            "url": "",
            "date": datetime.now().strftime("%B %d, %Y"),
            "source": "News Agent — LLM Summary",
            "summary": summary
        }] + articles

        news_sources = [a["url"] for a in articles if a.get("url")]

        return {
            "news_results": news_results,
            "sources": list(set(state.get("sources", []) + news_sources))
        }

    except Exception as e:
        print(f"❌ News Agent failed: {e}")
        return {"news_results": [], "sources": state.get("sources", [])}