from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from src.workflow import router, synthesizer


def test_router_uses_structured_intents_and_limits_duplicates(monkeypatch):
    observed = {}

    class StructuredModel:
        def invoke(self, messages):
            observed["messages"] = messages
            return SimpleNamespace(intents=["tax_agent", "news_agent", "tax_agent", "market_agent"])

    class Model:
        def with_structured_output(self, schema):
            assert schema is router.RouteDecision
            return StructuredModel()

    monkeypatch.setattr(router, "get_llm", lambda key: Model())
    state = {
        "messages": [HumanMessage(content="Earlier"), AIMessage(content="Answer"),
                     HumanMessage(content="tax and news")],
        "portfolio_shared": True,
    }

    result = router.router_node(state)

    assert result == {"intents": ["tax_agent", "news_agent", "market_agent"],
                      "intent": "tax_agent", "agent_outputs": None}
    assert observed["messages"][0][0] == "system"
    assert observed["messages"][-1].content == "tax and news"


def test_router_falls_back_to_keywords_on_model_error(monkeypatch):
    class Model:
        def with_structured_output(self, schema):
            raise RuntimeError("offline")

    monkeypatch.setattr(router, "get_llm", lambda key: Model())
    result = router.router_node({"messages": [HumanMessage(content="Tax, latest news and Nasdaq market")]})
    assert result["intents"] == ["tax_agent", "news_agent", "market_agent"]


def test_router_normalization_and_fanout_are_bounded():
    assert router.normalize_intents(["", "news_agent", "news_agent", "tax_agent", "market_agent"]) == [
        "news_agent", "tax_agent", "market_agent"
    ]
    assert router.normalize_intents([]) == ["finance_qa_agent"]
    sends = router.route_to_agents({"intents": ["tax_agent", "news_agent", "tax_agent", "market_agent"]})
    assert [send.node for send in sends] == ["tax_agent", "news_agent", "market_agent"]


def test_synthesizer_empty_and_single_output_paths():
    empty = synthesizer.synthesizer_node({"agent_outputs": []})
    assert "could not produce an answer" in empty["messages"][0].content

    single = synthesizer.synthesizer_node({
        "intents": ["tax_agent"],
        "agent_outputs": [{"agent": "tax_agent", "raw": "Original answer", "content": "Original answer",
                           "sources": ["tax.md"]}],
    })
    assert single["messages"][0].content == "Original answer"
    assert single["messages"][0].name == "tax_agent"
    assert single["active_agent"] == "tax_agent"
    assert single["sources"] == ["tax.md"]


def test_synthesizer_orders_answers_and_falls_back_on_model_error(monkeypatch):
    def fail(*args):
        raise RuntimeError("model offline")

    monkeypatch.setattr(synthesizer, "get_llm", lambda key: SimpleNamespace(invoke=fail))
    result = synthesizer.synthesizer_node({
        "messages": [HumanMessage(content="Tax and news?")],
        "intents": ["news_agent", "tax_agent"],
        "agent_outputs": [
            {"agent": "tax_agent", "content": "Tax details", "sources": ["tax.md"]},
            {"agent": "news_agent", "content": "News details", "sources": ["news.md", "tax.md"]},
        ],
    })

    text = result["messages"][0].content
    assert text.index("News details") < text.index("Tax details")
    assert text.count("General educational information only") == 1
    assert result["active_agent"] == "news_agent, tax_agent"
    assert result["sources"] == ["news.md", "tax.md"]


def test_agent_node_converts_response_to_synthesis_payload():
    from src.workflow.graph import agent_node

    class FakeAgent:
        key = "market_agent"

        def run(self, state):
            return {"messages": [AIMessage(content="Market answer.\n\n---\n" + synthesizer.add_disclaimer("x"))],
                    "sources": ["market.md"]}

    result = agent_node(FakeAgent())({"messages": [HumanMessage(content="markets?")]})
    assert result["agent_outputs"][0]["agent"] == "market_agent"
    assert result["agent_outputs"][0]["content"].startswith("Market answer.")
    assert result["agent_outputs"][0]["sources"] == ["market.md"]
