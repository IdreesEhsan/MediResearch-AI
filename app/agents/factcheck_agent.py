# ============================================================
# app/agents/factcheck_agent.py
# ============================================================
# Fact-Check Agent — Phase 2 (Sequential, Step 2)
#
# Validates every major claim in the summary against the
# original source materials and assigns a confidence score.
#
# Flow:
#   1. Read summary from state
#   2. Compare each claim against search and RAG results
#   3. Mark each claim as VERIFIED / UNVERIFIED / CONTRADICTED
#   4. Assign overall confidence score 0-100
#   5. Write results back to state
# ============================================================

import json as json_module
from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.utils.config import config
from app.utils.prompts import FACT_CHECK_AGENT_PROMPT
from app.utils.langsmith_config import trace_agent
from app.graph.state import ResearchState


# ── LLM Setup ─────────────────────────────────────────────────
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=0.0,   # Zero temperature for fact checking
                       # We want deterministic, not creative answers
    max_tokens=config.GROQ_MAX_TOKENS
)

def parse_fact_check_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the LLM's JSON response into a structured dict.
    Handles cases where LLM wraps JSON in code blocks.
    """
    # Remove markdown code blocks if present
    # LLM sometimes returns ```json ... ``` around the JSON
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        # Remove opening ```json or ``` line
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        # Remove closing ``` line
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        return json_module.loads(cleaned)
    except json_module.JSONDecodeError:
        # Try finding JSON block by braces
        try:
            start = cleaned.find("{")
            end   = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                return json_module.loads(cleaned[start:end])
        except json_module.JSONDecodeError:
            pass

    # Default fallback if all parsing fails
    return {
        "fact_check_results": [
            {
                "claim":  "Unable to parse fact-check results",
                "status": "UNVERIFIED",
                "source": "N/A",
                "note":   "JSON parsing failed"
            }
        ],
        "confidence_score":   50,
        "overall_assessment": "Manual review recommended",
        "recommendation":     "REVISE"
    }
    
def format_sources_for_check(search_results: List[Dict], rag_results: List[Dict]) -> str:
    """
    Combine search and RAG results into one source string
    for the fact-check prompt.

    Args:
        search_results: Results from Search Agent.
        rag_results:    Validated chunks from RAG Agent.

    Returns:
        Combined formatted source string.
    """
    sources_text = "=== WEB SEARCH SOURCES ===\n"

    # Add top 3 search results
    for i, r in enumerate(search_results[:3], 1):
        sources_text += (
            f"[{i}] {r.get('title', '')}\n"
            f"{r.get('snippet', '')[:300]}\n\n"
        )
    
    sources_text += "\n=== KNOWLEDGE BASE SOURCES ===\n"
    
    # Add top 3 RAG chunks
    for i, r in enumerate(rag_results[:3], 1):
        sources_text += (
            f"[{i}] {r.get('source', '')}\n"
            f"    {r.get('text', '')[:300]}\n\n"
        )

    return sources_text

def run_factcheck_agent(state: ResearchState) -> ResearchState:
    """
    Main Fact-Check Agent — called by LangGraph as a node.

    Reads from state:  summary, search_results, rag_results, query
    Writes to state:   fact_check_results, confidence_score

    Args:
        state: Current ResearchState from LangGraph.

    Returns:
        Updated state with fact_check_results and confidence_score.
    """
    print("🔎 Fact-Check Agent running...")

    query   = state["query"]
    summary = state.get("summary", "")
    
    if not summary:
        print("   ⚠️  No summary to fact-check — skipping")
        return {
            **state,
            "fact_check_results": [],
            "confidence_score":   0
        }

    try:
        # Step 1: Format source materials for comparison
        sources_text = format_sources_for_check(
            state.get("search_results", []),
            state.get("rag_results", [])
        )

        print("   Validating claims against sources...")
        
        # Step 2: Fill in fact-check prompt
        prompt = FACT_CHECK_AGENT_PROMPT.format(
            query          = query,
            summary        = summary,
            search_results = sources_text,
            rag_results    = ""   # Already included in sources_text
        )
        
        # Step 3: Ask LLM to validate each claim
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Step 4: Parse the JSON response
        parsed = parse_fact_check_response(response.content)

        fact_check_results = parsed.get("fact_check_results", [])
        confidence_score   = parsed.get("confidence_score", 50)
        recommendation     = parsed.get("recommendation", "REVISE")
        
        # Count verified vs unverified claims
        verified   = sum(1 for r in fact_check_results if r.get("status") == "VERIFIED")
        unverified = sum(1 for r in fact_check_results if r.get("status") == "UNVERIFIED")
        contradicted = sum(1 for r in fact_check_results if r.get("status") == "CONTRADICTED")

        print(f"   ✅ Fact-check complete:")
        print(f"      Verified:     {verified}")
        print(f"      Unverified:   {unverified}")
        print(f"      Contradicted: {contradicted}")
        print(f"      Confidence:   {confidence_score}/100")
        print(f"      Recommendation: {recommendation}")

        return {
            **state,
            "fact_check_results": fact_check_results,
            "confidence_score":   confidence_score
        }
    
    except Exception as e:
        print(f"❌ Fact-Check Agent failed: {e}")
        return {
            **state,
            "fact_check_results": [],
            "confidence_score":   0,
            "error":              f"Fact-Check Agent error: {str(e)}"
        }