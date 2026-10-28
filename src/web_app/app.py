"""Streamlit UI.   Run from project root:   streamlit run src/web_app/app.py"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st

from src.workflow.graph import ask, build_graph

st.set_page_config(page_title="AI Finance Assistant", page_icon="💹", layout="wide")
st.title("💹 AI Finance Assistant")
st.caption("Educational only - not financial, investment, or tax advice.")


@st.cache_resource
def get_graph():
    return build_graph()


if "thread_id" not in st.session_state:
    st.session_state.thread_id, st.session_state.history = str(uuid.uuid4()), []

with st.sidebar:
    st.header("Portfolio (optional)")
    df = st.data_editor(
        pd.DataFrame({"ticker": ["AAPL", "VTI"], "shares": [10.0, 25.0], "cost_basis": [150.0, 200.0]}),
        num_rows="dynamic",
    )
    share = st.checkbox("Share this portfolio with the assistant")
    if st.button("New conversation"):
        st.session_state.thread_id, st.session_state.history = str(uuid.uuid4()), []
        st.rerun()

for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("agent"):
            st.caption(f"Agent: {m['agent']}" + (f" | Sources: {', '.join(m['sources'])}" if m["sources"] else ""))

if prompt := st.chat_input("Ask about investing, your goals, the markets, taxes..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    portfolio = df.dropna(subset=["ticker", "shares"]).to_dict("records") if share else []
    with st.chat_message("assistant"), st.spinner("Thinking..."):
        out = ask(get_graph(), prompt, st.session_state.thread_id, portfolio)
        answer = out["messages"][-1].content
        st.markdown(answer)
        st.caption(f"Agent: {out['active_agent']}" + (f" | Sources: {', '.join(out['sources'])}" if out["sources"] else ""))
    st.session_state.history.append({"role": "assistant", "content": answer,
                                     "agent": out["active_agent"], "sources": out.get("sources", [])})
