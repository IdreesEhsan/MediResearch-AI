# ============================================================
# app/graph/router.py
# ============================================================
# Conditional Router — decides workflow paths based on state.
#
# LangGraph uses these functions to determine which node
# to visit next after each step.
#
# Two routing decisions:
#   1. after_hitl_router  → APPROVED goes to Report Agent
#                         → REJECTED loops back to agents
#   2. focus_area_router  → Routes to different agent configs
#                           based on research domain
# ============================================================

from app.graph.state import ResearchState, HITLDecision


def after_hitl_router(state: ResearchState) -> str:
    """
    Routes the workflow after the HITL approval gate.

    Called by LangGraph after the HITL node completes.
    Returns the name of the next node to visit.

    Decision logic:
        APPROVED → "report_agent"   (generate final report)
        REJECTED → "memory_load"    (loop back with doctor notes)
        PENDING  → "hitl"           (stay at HITL — not reviewed yet)

    Args:
        state: Current ResearchState with hitl_decision set.

    Returns:
        Name of the next LangGraph node to execute.
    """
    decision = state.get("hitl_decision", HITLDecision.PENDING)
    
    if decision == HITLDecision.APPROVED:
        print("✅ HITL: APPROVED → proceeding to Report Agent")
        return "report_agent"
    
    elif decision == HITLDecision.REJECTED:
        # Check retry count to prevent infinite loops
        retry_count = state.get("retry_count", 0)
        
        if retry_count >= 3:
            # Max retries reached — force approve to prevent infinite loop
            print("   ⚠️  Max retries reached — forcing completion")
            return "report_agent"

        print(f"   ❌ HITL: REJECTED → looping back (retry {retry_count + 1}/3)")
        return "summarizer_agent"   # Go back to summarizer with doctor notes

    else:
        # Still pending — wait for doctor review
        print("   ⏳ HITL: PENDING — awaiting doctor review")
        return "hitl_node"
    
def should_use_news(state: ResearchState) -> bool:
    """
    Determines if the News Agent should run for this query.

    News Agent is most valuable for:
    - News-focused research (always run)
    - Disease research (recent outbreaks, new treatments)
    - General queries (recent developments)

    Less valuable for:
    - Drug research (FDA approvals change slowly)

    Args:
        state: Current ResearchState.

    Returns:
        True if News Agent should run, False otherwise.
    """
    focus_area = str(state.get("focus_area", "general"))
    
    # Always run news for these focus areas
    if focus_area in ["news", "disease", "general"]:
        return True
    
    # For drug research run news only if query mentions recent/new/latest
    query = state.get("query", "").lower()
    if any(word in query for word in ["recent", "new", "latest", "2024", "2025"]):
        return True
    
    return False

def error_router(state: ResearchState) -> str:
    """
    Routes the workflow when an error occurs.

    If an error is present in state, skip to the end
    instead of continuing with bad data.

    Args:
        state: Current ResearchState.

    Returns:
        'end' if error present, 'continue' otherwise.
    """
    if state.get("error"):
        print(f"   ⚠️  Error detected: {state['error']}")
        print("   Routing to end — check logs for details")
        return "end"
    
    return "continue"