# ============================================================
# app/utils/langsmith_config.py
# ============================================================
# Sets up LangSmith so every LLM call, tool use, and agent
# step is automatically logged to your LangSmith dashboard.
#
# Dashboard: https://smith.langchain.com
# ============================================================

import os
from functools import wraps
from app.utils.config import config

def setup_langsmith() -> None:
    """
    Configure LangSmith by setting the required environment variables.

    Call this ONCE at application startup — after that, every
    LangChain and LangGraph call is automatically traced.
    No extra code needed inside each agent.
    """
    os.environ["LANGSMITH_TRACING_V2"] = config.LANGSMITH_TRACING_V2
    os.environ["LANGSMITH_API_KEY"] = config.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"]     = config.LANGSMITH_PROJECT
    
    print(f"✅ LangSmith tracing enabled → project: '{config.LANGSMITH_PROJECT}'")

def trace_agent(agent_name: str):
    """
    Decorator that wraps an agent function with a named LangSmith span.

    This lets you see each agent as a separate named block in LangSmith
    so you can track exactly how long each agent took and what it returned.

    Usage:
        @trace_agent("search_agent")
        def run(state):
            ...

    Args:
        agent_name: The label shown in the LangSmith trace UI.
    """
    def decorator(func):
        @wraps(func)    # Preserves the original function name and docstring
        def wrapper(*args, **kwargs):
            try:
                from langsmith import traceable
                traced = traceable(
                    name=agent_name,
                    run_type="chain"
                )(func)
                
                return traced(*args, **kwargs)
            except ImportError:
                # If LangSmith is not installed, just run without tracing
                # This prevents the whole app from crashing if tracing is down
                return func(*args, **kwargs)
            
        return wrapper
    return decorator

def trace_export(export_format: str):
    """
    Decorator specifically for export operations (PDF or Word).
    Tags the LangSmith span as a 'tool' run type.

    Usage:
        @trace_export("pdf")
        def generate_pdf(session_id, report):
            ...

    Args:
        export_format: Either "pdf" or "word"
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from langsmith import traceable
                traced = traceable(
                    name=f"export_{export_format}",
                    run_type="tool"     # "tool" = a single utility action
                )(func)

                return traced(*args, **kwargs)

            except ImportError:
                return func(*args, **kwargs)

        return wrapper
    return decorator