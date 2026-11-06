from types import SimpleNamespace

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.goal_planning_agent import GoalParams, GoalPlanningAgent
from src.agents.market_agent import MarketAgent
from src.agents.news_agent import NewsAgent
from src.agents.portfolio_agent import PortfolioAgent
from src.core import base_agent
from src.utils.guardrails import DISCLAIMER


def uninitialized(agent_class):
    return object.__new__(agent_class)


def test_base_agent_skips_retrieval_when_disabled_or_query_empty(monkeypatch):
    monkeypatch.setattr(base_agent, "retrieve", lambda *args: (_ for _ in ()).throw(AssertionError()))
    agent = uninitialized(base_agent.BaseAgent)
    agent.use_rag = False
    agent.namespaces = ["finance_qa"]
    assert agent._retrieve("question") == ([], False)

    agent.use_rag = True
    assert agent._retrieve("") == ([], False)


def test_base_agent_handles_retrieval_and_live_context_failures(monkeypatch):
    observed = {}
    agent = uninitialized(base_agent.BaseAgent)
    agent.key = "finance_qa"
    agent.namespaces = ["finance_qa"]
    agent.use_rag = True
    agent.history_window = 10
    agent.log = base_agent.get_logger("test.agent")
    agent.gather_context = lambda state: (_ for _ in ()).throw(RuntimeError("provider detail"))
    agent.llm = SimpleNamespace(
        invoke=lambda messages: (observed.update(messages=messages) or AIMessage(content="A general answer."))
    )
    monkeypatch.setattr(base_agent, "retrieve", lambda *args: (_ for _ in ()).throw(RuntimeError("offline")))

    result = agent.run({"messages": [HumanMessage(content="What is a bond?")]})

    assert result["sources"] == []
    assert "knowledge base was unavailable" in result["messages"][0].content
    assert "Live data was unavailable" in observed["messages"][0].content
    assert result["messages"][0].content.endswith(DISCLAIMER)


def test_base_agent_includes_retrieved_sources_and_live_context(monkeypatch):
    doc = Document(page_content="Bonds are loans.", metadata={"source": "bonds.md"})
    prompts = {}
    agent = uninitialized(base_agent.BaseAgent)
    agent.key = "finance_qa"
    agent.namespaces = ["finance_qa"]
    agent.use_rag = True
    agent.history_window = 10
    agent.system_prompt = "Finance education."
    agent.gather_context = lambda state: "Current data."
    agent.llm = SimpleNamespace(
        invoke=lambda messages: (prompts.update(messages=messages) or AIMessage(content="A sourced answer."))
    )
    monkeypatch.setattr(base_agent, "retrieve", lambda *args: [doc])

    result = agent.run({"messages": [HumanMessage(content="What is a bond?")]})

    assert result["sources"] == ["bonds.md"]
    assert "Bonds are loans." in prompts["messages"][0].content
    assert "Current data." in prompts["messages"][0].content
    assert result["messages"][0].content.startswith("A sourced answer.")


def test_specialist_agents_build_expected_mcp_requests(monkeypatch):
    from src.agents import goal_planning_agent, market_agent, news_agent, portfolio_agent

    monkeypatch.setattr(market_agent, "load_config", lambda: {"data": {"default_indices": ["^GSPC"]}})
    monkeypatch.setattr(market_agent, "call_mcp_tools", lambda calls: [{"quotes": [], "missing": ["^GSPC"]}])
    monkeypatch.setattr(market_agent, "format_quotes", lambda quotes: "No quote data.")
    context = uninitialized(MarketAgent).gather_context({"messages": [HumanMessage(content="How is AAPL?")]})
    assert "Some requested quotes are unavailable: ^GSPC" in context
    context = uninitialized(MarketAgent).gather_context({"messages": [HumanMessage(content="AAPL price?")]})
    assert "No quote data." in context

    news_calls = []
    monkeypatch.setattr(news_agent, "load_config", lambda: {"data": {"max_news_items": 4}})
    monkeypatch.setattr(news_agent, "call_mcp_tools", lambda calls: news_calls.append(calls) or [
        {"items": [{"title": "Rates"}], "some_feeds_failed": True}
    ])
    monkeypatch.setattr(news_agent, "format_news", lambda items: f"{len(items)} headlines")
    news_context = uninitialized(NewsAgent).gather_context(
        {"messages": [HumanMessage(content="Summarize interest rates news")]}
    )
    assert news_calls[0][0][1]["limit"] == 4
    assert "Some news sources are unavailable" in news_context

    portfolio_calls = []
    monkeypatch.setattr(portfolio_agent, "call_mcp_tools", lambda calls: portfolio_calls.append(calls) or [
        {"rows": []}
    ])
    monkeypatch.setattr(portfolio_agent, "format_portfolio_report", lambda result: "Portfolio report.")
    portfolio_agent_instance = uninitialized(PortfolioAgent)
    assert "NO PORTFOLIO" in portfolio_agent_instance.gather_context({})
    assert portfolio_agent_instance.gather_context({"portfolio": [{"ticker": "MSFT", "shares": 1}]}) == "Portfolio report."
    assert portfolio_calls[0][0][1]["holdings"][0]["ticker"] == "MSFT"


def test_goal_planning_agent_handles_missing_and_computes_scenarios(monkeypatch):
    from src.agents import goal_planning_agent

    agent = uninitialized(GoalPlanningAgent)

    class Extractor:
        def __init__(self, params):
            self.params = params

        def invoke(self, messages):
            return self.params

    class Model:
        params = GoalParams(target_amount=None)

        def with_structured_output(self, model):
            assert model is GoalParams
            return Extractor(self.params)

    model = Model()
    agent.llm = model
    state = {"messages": [HumanMessage(content="Help me save")]}
    assert "Missing target amount" in agent.gather_context(state)

    model.params = GoalParams(
        goal_name="home", target_amount=100_000, years=10, current_savings=5_000,
        monthly_contribution=500,
    )
    monkeypatch.setattr(goal_planning_agent, "agent_cfg", lambda key: {"default_annual_return": 0.06})
    calls = []

    def calculate(batch):
        calls.extend(batch)
        return [
            {"required_monthly_contribution": 250.0},
            {"future_value": 80_000.0},
            {"required_monthly_contribution": 200.0},
            {"future_value": 90_000.0},
            {"required_monthly_contribution": 150.0},
            {"future_value": 100_000.0},
        ]

    monkeypatch.setattr(goal_planning_agent, "call_mcp_tools", calculate)
    context = agent.gather_context(state)
    assert len(calls) == 6
    assert "Goal: home" in context
    assert "saving $500/month would reach $80,000" in context
    assert "aggressive (8.0%)" in context

    model.params = GoalParams(target_amount=10_000, years=2, expected_annual_return=0.05)
    calls.clear()
    monkeypatch.setattr(goal_planning_agent, "call_mcp_tools", calculate)
    agent.gather_context(state)
    assert len(calls) == 1
    assert calls[0][1]["annual_rate"] == 0.05
