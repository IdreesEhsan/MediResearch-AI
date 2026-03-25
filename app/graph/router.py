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
    """Routes after HITL node. FIXED: now correctly returns 'retry_node'."""
    decision = state.get("hitl_decision", HITLDecision.PENDING)

    if decision == HITLDecision.APPROVED:
        print("✅ HITL: APPROVED → proceeding to Report Agent")
        return "report_agent"

    elif decision == HITLDecision.REJECTED:
        retry_count = state.get("retry_count", 0)
        if retry_count >= 3:
            print("   ⚠️  Max retries reached — forcing completion")
            return "report_agent"
        print(f"   ❌ HITL: REJECTED → retry_node (retry {retry_count + 1}/3)")
        return "retry_node"          # ← This was the main bug

    else:
        print("   ⏳ HITL: PENDING — awaiting doctor review")
        return "hitl_node"