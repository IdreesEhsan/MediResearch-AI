# ============================================================
# app/agents/rag_agent.py
# ============================================================
# RAG Agent — Phase 1 (Parallel)
#
# Retrieves relevant medical knowledge from Pinecone using
# CRAG validation to filter out low-quality chunks.
#
# Flow:
#   1. Take user query from state
#   2. Run CRAG retrieval (Pinecone + scoring + filtering)
#   3. If no chunks pass → activate web search fallback
#   4. Return validated results to state
# ============================================================

from typing import List, Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.utils.config import config
from app.utils.prompts import RAG_AGENT_PROMPT
from app.utils.langsmith_config import trace_agent
from app.graph.state import ResearchState
from app.rag.crag import CRAGRetriever
from app.rag.embeddings import embedder

# ── LLM Setup ─────────────────────────────────────────────────
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=config.GROQ_TEMPERATURE,
    max_tokens=config.GROQ_MAX_TOKENS
)

# ── CRAG Retriever ────────────────────────────────────────────
# Initialize once — connects to Pinecone on startup
retriever = CRAGRetriever()

def format_rag_results(crag_result) -> List[Dict[str, Any]]:
    """
    Convert CRAG result into a list of dicts for the state.

    Each dict contains the chunk text, source, and score
    so downstream agents can reference them correctly.

    Args:
        crag_result: CRAGResult object from retriever.

    Returns:
        List of {text, source, score, label} dicts.
    """
    results = []
    for chunk in crag_result.passed_chunks:
        results.append({
            "text": chunk.text,
            "source": chunk.source,
            "score": round(chunk.score, 3),
            "label": chunk.label.value      # RELEVANT OR PARTIAL 
        })
    
    return results

def generate_rag_answer(query: str, focus_area: str, context: str) -> str:
    """
    Use the LLM to generate an answer grounded in retrieved context.

    The LLM is explicitly told to only use the provided context
    and cite sources — this prevents hallucination.

    Args:
        query:      The research question.
        focus_area: Research domain.
        context:    Validated chunks from CRAG as a formatted string.

    Returns:
        LLM-generated answer grounded in the context.
    """
    prompt = RAG_AGENT_PROMPT.format(
        query=query,
        focus_area=focus_area,
        context=context
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

@trace_agent("rag_agent")
def run_rag_agent(state: ResearchState) -> ResearchState:
    """
    Main RAG Agent function — called by LangGraph as a node.

    Reads from state:  query, focus_area, sources
    Writes to state:   rag_results, sources

    Args:
        state: Current ResearchState from LangGraph.

    Returns:
        Updated state with rag_results and sources filled in.
    """
    print("RAG Agent running...")
    
    query = state['query']
    focus_area = state['focus_area']
    
    try:
        # Step 1: Run CRAG retrieval
        # This queries Pinecone, scores every chunk, and filters
        print("   Running CRAG retrieval...")
        crag_result = retriever.retrieve_and_validate(query)
        
        # Step 2: Check if fallback is needed
        if crag_result.used_fallback:
            # No chunks passed — knowledge base doesn't have enough info
            # Return empty results — Search Agent will cover this gap
            print("   ⚠️  No relevant chunks found — fallback to web search")
            return {
                **state,
                "rag_results": [],
                "sources":     state.get("sources", [])
            }
            
        # Step 3: Format results for state
        rag_results = format_rag_results(crag_result)
        print(f"   ✅ {len(rag_results)} validated chunks retrieved")

        # Step 4: Generate a grounded answer using retrieved context
        print("   Generating grounded answer...")
        answer = generate_rag_answer(query, focus_area, crag_result.context)

        # Add the LLM answer as the first result for easy access
        rag_results.insert(0, {
            "text":   answer,
            "source": "RAG Agent — Knowledge Base Summary",
            "score":  1.0,
            "label":  "SUMMARY"
        })
        
        # Merge new sources with existing ones from Search Agent
        all_sources = list(set(
            state.get("source", []) + crag_result.sources
        ))
        
        return {
            **state,
            "rag_results": rag_results,
            "sources": all_sources
        }
        
    except Exception as e:
        print(f"❌ RAG Agent failed: {e}")
        return {
            **state,
            "rag_results": [],
            "error":       f"RAG Agent error: {str(e)}"
        }