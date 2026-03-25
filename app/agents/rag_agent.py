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

# LLM Setup
llm = ChatGroq(
    api_key=config.GROQ_API_KEY,
    model=config.GROQ_MODEL,
    temperature=config.GROQ_TEMPERATURE,
    max_tokens=config.GROQ_MAX_TOKENS
)

retriever = CRAGRetriever()

def format_rag_results(crag_result) -> List[Dict[str, Any]]:
    results = []
    for chunk in crag_result.passed_chunks:
        results.append({
            "text": chunk.text,
            "source": chunk.source,
            "score": round(chunk.score, 3),
            "label": chunk.label.value
        })
    return results

def generate_rag_answer(query: str, focus_area: str, context: str) -> str:
    prompt = RAG_AGENT_PROMPT.format(
        query=query,
        focus_area=focus_area,
        context=context
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

@trace_agent("rag_agent")
def run_rag_agent(state: ResearchState) -> ResearchState:
    print("RAG Agent running...")
    
    query = state['query']
    focus_area = state['focus_area']
    
    try:
        print("   Running CRAG retrieval...")
        crag_result = retriever.retrieve_and_validate(query)
        
        if crag_result.used_fallback:
            print("   ⚠️  No relevant chunks found — fallback to web search")
            return {
                **state,
                "rag_results": [],
                "sources": state.get("sources", [])
            }
        
        rag_results = format_rag_results(crag_result)
        print(f"   ✅ {len(rag_results)} validated chunks retrieved")

        print("   Generating grounded answer...")
        answer = generate_rag_answer(query, focus_area, crag_result.context)

        rag_results.insert(0, {
            "text": answer,
            "source": "RAG Agent — Knowledge Base Summary",
            "score": 1.0,
            "label": "SUMMARY"
        })
        
        all_sources = list(set(
            state.get("sources", []) + crag_result.sources
        ))
        
        return {
            "rag_results": rag_results,
            "sources": all_sources
        }
        
    except Exception as e:
        print(f"❌ RAG Agent failed: {e}")
        return {
            "rag_results": [],
            "error": f"RAG Agent error: {str(e)}"
        }