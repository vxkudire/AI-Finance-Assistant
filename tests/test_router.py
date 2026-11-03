import pytest

from src.workflow.router import keyword_fallback


@pytest.mark.parametrize("text,expected", [
    ("What are the tax implications of a Roth conversion?", "tax_agent"),
    ("Analyze my portfolio", "portfolio_agent"),
    ("I want to retire in 20 years, how much should I save?", "goal_planning_agent"),
    ("Summarize the latest news on interest rates", "news_agent"),
    ("What is the price of AAPL today?", "market_agent"),
    ("What is an ETF?", "finance_qa_agent"),
])
def test_keyword_fallback(text, expected):
    assert keyword_fallback(text) == expected

def test_keyword_fallback_multi():
    from src.workflow.router import keyword_fallback_multi
    assert keyword_fallback_multi("Tax on my portfolio and the latest news") == ["tax_agent", "portfolio_agent", "news_agent"]
    assert keyword_fallback_multi("What is an ETF?") == ["finance_qa_agent"]


def test_graph_routes_to_multiple_agents_and_synthesizes(monkeypatch):
    from types import SimpleNamespace
    from langchain_core.messages import AIMessage
    from src.workflow import graph as g, synthesizer as syn

    class Fake:
        def __init__(self, key):
            self.key = key
        def run(self, state):
            return {"messages": [AIMessage(content=f"{self.key} answer")], "sources": [self.key + ".md"]}

    monkeypatch.setattr(g, "AGENT_CLASSES", {k: (lambda k=k: Fake(k)) for k in g.AGENT_CLASSES})
    monkeypatch.setattr(g, "router_node", lambda s: {"intents": ["tax_agent", "news_agent"], "intent": "tax_agent", "agent_outputs": None})
    monkeypatch.setattr(syn, "get_llm", lambda *_: SimpleNamespace(invoke=lambda m: AIMessage(content="merged")))
    graph = g.build_graph()
    out = g.ask(graph, "tax and news", "t1")
    assert out["messages"][-1].content.startswith("merged")
    assert out["active_agent"] == "tax_agent, news_agent"
    assert out["sources"] == ["news_agent.md", "tax_agent.md"]
    out = g.ask(graph, "again", "t1")
    assert len(out["agent_outputs"]) == 2
