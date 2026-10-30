"""LangGraph assembly:   START -> router -> (one of six agents) -> END, with conversation memory per thread."""
import os

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents import AGENT_CLASSES
from src.core.state import AgentState
from src.workflow.router import route_to_agent, router_node


def thread_id_for_user(username: str) -> str:
    """Return a stable, case-insensitive checkpoint ID for a username."""
    normalized = username.strip().casefold()
    if not normalized:
        raise ValueError("Username must not be empty.")
    return f"user:{normalized}"


def make_checkpointer():
    """PostgresSaver when POSTGRES_URL is set (persists across restarts); otherwise in-process MemorySaver."""
    url = os.getenv("POSTGRES_URL")
    if not url:
        return MemorySaver()
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        url, max_size=5, open=True,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    try:
        saver = PostgresSaver(pool)
        saver.setup()       # creates checkpoint tables if missing
        return saver
    except Exception:
        pool.close()
        raise


def close_checkpointer(checkpointer: object) -> None:
    """Close resources owned by a checkpointer, if it has any."""
    conn = getattr(checkpointer, "conn", None)
    if conn is not None:
        conn.close()


def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("router", router_node)
    for key, cls in AGENT_CLASSES.items():
        g.add_node(key, cls().run)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_to_agent, {k: k for k in AGENT_CLASSES})
    for key in AGENT_CLASSES:
        g.add_edge(key, END)
    return g.compile(checkpointer=checkpointer or make_checkpointer())


def ask(compiled_graph, text: str, thread_id: str = "default", portfolio: list[dict] | None = None) -> dict:
    payload: dict = {"messages": [HumanMessage(content=text)]}
    if portfolio is not None:           # [] clears a previously supplied portfolio
        payload["portfolio"] = portfolio
    return compiled_graph.invoke(payload, config={"configurable": {"thread_id": thread_id}})


if __name__ == "__main__":      # python -m src.workflow.graph
    username = ""
    while not username:
        username = input("Username: ").strip()
        if not username:
            print("Username cannot be empty.")
    checkpointer, tid = make_checkpointer(), thread_id_for_user(username)
    try:
        graph = build_graph(checkpointer)
        print("AI Finance Assistant - type 'quit' to exit")
        while (q := input("\nYou: ").strip()).lower() not in {"quit", "exit"}:
            out = ask(graph, q, tid)
            print(f"\n[{out['active_agent']}] {out['messages'][-1].content}")
            if out.get("sources"):
                print("Sources:", ", ".join(out["sources"]))
    finally:
        close_checkpointer(checkpointer)
