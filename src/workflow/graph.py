"""LangGraph assembly:   START -> router -> (one of six agents) -> END,  with conversation memory per thread."""
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents import AGENT_CLASSES
from src.core.state import AgentState
from src.workflow.router import route_to_agent, router_node


def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("router", router_node)
    for key, cls in AGENT_CLASSES.items():
        g.add_node(key, cls().run)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_to_agent, {k: k for k in AGENT_CLASSES})
    for key in AGENT_CLASSES:
        g.add_edge(key, END)
    # MemorySaver = in-process memory. Use SqliteSaver / PostgresSaver for persistence across restarts.
    return g.compile(checkpointer=checkpointer or MemorySaver())


def ask(graph, text: str, thread_id: str = "default", portfolio: list[dict] | None = None) -> dict:
    payload: dict = {"messages": [HumanMessage(content=text)]}
    if portfolio is not None:           # [] clears a previously supplied portfolio
        payload["portfolio"] = portfolio
    return graph.invoke(payload, config={"configurable": {"thread_id": thread_id}})


if __name__ == "__main__":      # python -m src.workflow.graph
    graph, tid = build_graph(), str(uuid.uuid4())
    print("AI Finance Assistant - type 'quit' to exit")
    while (q := input("\nYou: ").strip()).lower() not in {"quit", "exit"}:
        out = ask(graph, q, tid)
        print(f"\n[{out['active_agent']}] {out['messages'][-1].content}")
        if out.get("sources"):
            print("Sources:", ", ".join(out["sources"]))
