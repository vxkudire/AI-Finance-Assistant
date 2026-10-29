"""Intent router: LLM structured-output classifier with a keyword fallback if the LLM call fails."""
from typing import Literal

from pydantic import BaseModel, Field

from src.core.llm_factory import get_llm
from src.core.state import AgentState
from src.utils.helpers import last_user_text
from src.utils.logger import get_logger

log = get_logger("router")
Intent = Literal["finance_qa_agent", "portfolio_agent", "market_agent", "goal_planning_agent", "news_agent", "tax_agent"]


class RouteDecision(BaseModel):
    intent: Intent = Field(description="The single best agent for the user's latest message")


ROUTER_PROMPT = """Classify the user's latest message into exactly one intent:
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


def keyword_fallback(text: str) -> str:
    t = text.lower()
    for intent, words in _KEYWORDS:
        if any(w in t for w in words):
            return intent
    return "finance_qa_agent"


def router_node(state: AgentState) -> dict:
    query = last_user_text(state["messages"])
    try:
        decision = get_llm("router").with_structured_output(RouteDecision).invoke(
            [("system", ROUTER_PROMPT), *state["messages"][-4:]])
        intent = decision.intent
    except Exception as exc:
        log.warning("LLM routing failed (%s); using keyword fallback", exc)
        intent = keyword_fallback(query)
    log.info("routed -> %s", intent)
    return {"intent": intent}


def route_to_agent(state: AgentState) -> str:
    return state.get("intent", "finance_qa_agent")
