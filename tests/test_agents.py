from app.agents import search_agent
from app.graph.state import initial_state


def test_search_agent_empty_results(monkeypatch):
    # Ensure the agent handles empty results gracefully without raising
    monkeypatch.setattr(search_agent, "search_with_tavily", lambda queries: [])

    state = initial_state("diabetes treatment options", "disease")
    output = search_agent.run_search_agent(state)

    assert "search_results" in output
    assert isinstance(output["search_results"], list)
    assert output["search_results"] == []
    assert output.get("sources") == []
