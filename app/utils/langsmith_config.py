# ============================================================
# app/utils/langsmith_config.py
# ============================================================
# LangSmith Observability — instruments every agent with
# named spans so you can see exactly what each agent did,
# how long it took, and what it returned.
#
# Dashboard: https://smith.langchain.com
# ============================================================

import os
from functools import wraps
from app.utils.config import config


def setup_langsmith() -> None:
    """
    Configure LangSmith by setting required environment variables.
    Call once at application startup in workflow.py.
    After this every LangChain and LangGraph call is auto-traced.
    """
    os.environ["LANGSMITH_TRACING_V2"] = config.LANGSMITH_TRACING_V2
    os.environ["LANGSMITH_API_KEY"]     = config.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"]     = config.LANGSMITH_PROJECT

    print(f"✅ LangSmith tracing enabled → project: '{config.LANGSMITH_PROJECT}'")


def trace_agent(agent_name: str):
    """
    Decorator that wraps an agent function with a named
    LangSmith span. Shows each agent as a separate block
    in the LangSmith trace UI.

    Usage:
        @trace_agent("search_agent")
        def run_search_agent(state):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get current run name from LangSmith if available
            try:
                from langsmith import traceable

                @traceable(name=agent_name, run_type="chain")
                def traced(*a, **kw):
                    return func(*a, **kw)

                return traced(*args, **kwargs)

            except Exception:
                # If tracing fails run without it
                # Never let tracing break the actual agent
                return func(*args, **kwargs)

        return wrapper
    return decorator


def trace_tool(tool_name: str):
    """
    Decorator for tool calls like web search or export.
    Shows as a 'tool' type span in LangSmith.

    Usage:
        @trace_tool("tavily_search")
        def search_with_tavily(queries):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from langsmith import traceable

                @traceable(name=tool_name, run_type="tool")
                def traced(*a, **kw):
                    return func(*a, **kw)

                return traced(*args, **kwargs)

            except Exception:
                return func(*args, **kwargs)

        return wrapper
    return decorator


def trace_export(export_format: str):
    """
    Decorator for export operations (PDF or Word).
    Tags the span as a tool run in LangSmith.

    Usage:
        @trace_export("pdf")
        def generate_pdf(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from langsmith import traceable

                @traceable(name=f"export_{export_format}", run_type="tool")
                def traced(*a, **kw):
                    return func(*a, **kw)

                return traced(*args, **kwargs)

            except Exception:
                return func(*args, **kwargs)

        return wrapper
    return decorator