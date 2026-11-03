"""Shared LangGraph state passed between the router and every agent."""
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


def merge_outputs(current: list[dict] | None, update: list[dict] | None) -> list[dict]:
    """Accumulate parallel agent outputs; `None` resets the list at the start of a turn."""
    return [] if update is None else [*(current or []), *update]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # full conversation (append-only reducer)
    intent: str                       # primary intent (first of `intents`)
    intents: list[str]                # all agents selected by the router for this turn
    agent_outputs: Annotated[list[dict], merge_outputs]  # [{agent, content, sources}] awaiting synthesis
    portfolio: Optional[list[dict]]   # [{ticker, shares, cost_basis?}]
    active_agent: str                 # which agent answered last
    sources: list[str]                # knowledge-base documents used for the last answer
