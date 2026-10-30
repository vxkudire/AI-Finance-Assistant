"""Streamlit UI.   Run from project root:   streamlit run src/web_app/app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from src.workflow.graph import ask, build_graph, close_checkpointer, thread_id_for_user

st.set_page_config(page_title="AI Finance Assistant", page_icon="💹", layout="wide")
st.title("💹 AI Finance Assistant")
st.caption("Educational only - not financial, investment, or tax advice.")


def release_graph(graph):
    close_checkpointer(graph.checkpointer)


@st.cache_resource(on_release=release_graph)
def get_graph():
    return build_graph()


with st.sidebar:
    username = st.text_input("Username").strip()
    st.caption("A username is only an identifier, not a login. Anyone entering it can access that conversation.")
    st.header("Portfolio (optional)")
    df = st.data_editor(
        pd.DataFrame({"ticker": ["AAPL", "VTI"], "shares": [10.0, 25.0], "cost_basis": [150.0, 200.0]}),
        num_rows="dynamic",
    )
    share = st.checkbox("Share this portfolio with the assistant")

thread_id = thread_id_for_user(username) if username else None
if thread_id and st.session_state.get("thread_id") != thread_id:
    st.session_state.thread_id = thread_id
    snapshot = get_graph().get_state({"configurable": {"thread_id": thread_id}})
    st.session_state.history = [
        {
            "role": "user" if isinstance(message, HumanMessage) else "assistant",
            "content": message.content,
            **({"agent": message.name} if isinstance(message, AIMessage) and message.name else {}),
        }
        for message in snapshot.values.get("messages", [])
        if isinstance(message, (HumanMessage, AIMessage))
    ]

if thread_id:
    for m in st.session_state.history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("agent"):
                st.caption(f"Agent: {m['agent']}" + (f" | Sources: {', '.join(m['sources'])}" if m.get("sources") else ""))

if not username:
    st.info("Enter a username in the sidebar to load or start your conversation.")
elif prompt := st.chat_input("Ask about investing, your goals, the markets, taxes..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    portfolio = df.dropna(subset=["ticker", "shares"]).to_dict("records") if share else []
    with st.chat_message("assistant"), st.spinner("Thinking..."):
        out = ask(get_graph(), prompt, thread_id, portfolio)
        answer = out["messages"][-1].content
        st.markdown(answer)
        st.caption(f"Agent: {out['active_agent']}" + (f" | Sources: {', '.join(out['sources'])}" if out["sources"] else ""))
    st.session_state.history.append({"role": "assistant", "content": answer,
                                     "agent": out["active_agent"], "sources": out.get("sources", [])})
