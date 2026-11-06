"""Intent router: LLM structured-output classifier (one or more agents) with a keyword fallback if the LLM call fails."""
from typing import Literal

from langgraph.types import Send
from pydantic import BaseModel, Field

from src.core.llm_factory import get_llm
from src.core.state import AgentState, conversation_context
from src.utils.helpers import last_user_text
from src.utils.logger import get_logger

log = get_logger("router")
Intent = Literal["finance_qa_agent", "portfolio_agent", "market_agent", "goal_planning_agent", "news_agent", "tax_agent"]


MAX_AGENTS = 3


class RouteDecision(BaseModel):
    intents: list[Intent] = Field(
        description="Every agent needed to fully answer the latest message, most relevant first (1-3)",
        min_length=1,
    )


ROUTER_PROMPT = """Select the agent(s) needed to answer the user's latest message. Choose ONE agent when the
message is about a single topic; choose several (at most 3) only when it clearly spans multiple topics.
- finance_qa_agent: general finance concepts/education (stocks, bonds, ETFs, risk, budgeting, compounding...)
- portfolio_agent: review/analysis of the user's own holdings, diversification, allocation
- market_agent: current prices, index/stock moves, market conditions, live data
- goal_planning_agent: setting or planning a savings/retirement/home/education goal, how much to save
- news_agent: summarising or explaining recent financial news/headlines
- tax_agent: tax concepts, capital gains, 401k/IRA/Roth/HSA/529 account types
Use earlier turns only to resolve follow-ups like 'and what about Roth?'."""
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [   # order = priority
    ("tax_agent", ("tax", "401k", "401(k)", "ira", "roth", "hsa", "529", "capital gain", "deduction")),
    ("portfolio_agent", ("my portfolio", "portfolio", "my holdings", "allocation", "rebalance", "diversif")),
    ("goal_planning_agent", ("goal", "retire", "save for", "saving for", "how much to save", "down payment", "college")),
    ("news_agent", ("news", "headline", "latest on", "what happened")),
    ("market_agent", ("price", "quote", "trading", "s&p", "nasdaq", "dow", "index", "rally", "sell-off")),
]


def keyword_fallback_multi(text: str) -> list[str]:
    t = text.lower()
    hits = [intent for intent, words in _KEYWORDS if any(w in t for w in words)]
    return hits[:MAX_AGENTS] or ["finance_qa_agent"]


def keyword_fallback(text: str) -> str:
    return keyword_fallback_multi(text)[0]


def normalize_intents(intents: list[str]) -> list[str]:
    seen = list(dict.fromkeys(i for i in intents if i))[:MAX_AGENTS]
    return seen or ["finance_qa_agent"]


def router_node(state: AgentState) -> dict:
    query = last_user_text(state["messages"])
    try:
        decision = get_llm("router").with_structured_output(RouteDecision).invoke(
            [("system", ROUTER_PROMPT), *conversation_context(state, 4)])
        intents = normalize_intents(decision.intents)
    except Exception as exc:
        log.warning("LLM routing failed (%s); using keyword fallback", type(exc).__name__)
        intents = keyword_fallback_multi(query)
    log.info("routed -> %s", intents)
    return {"intents": intents, "intent": intents[0], "agent_outputs": None}


def route_to_agents(state: AgentState) -> list[Send]:
    """Fan out: one Send per selected agent, each running in parallel on the full state."""
    return [Send(i, state) for i in normalize_intents(state.get("intents") or [state.get("intent", "")])]