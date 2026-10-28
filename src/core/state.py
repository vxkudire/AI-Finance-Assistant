"""Shared LangGraph state passed between the router and every agent."""
from typing import Annotated, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # full conversation (append-only reducer)
    intent: str                       # set by the router
    portfolio: Optional[list[dict]]   # [{ticker, shares, cost_basis?}]
    active_agent: str                 # which agent answered last
    sources: list[str]                # knowledge-base documents used for the last answer
