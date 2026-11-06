"""Streamlit UI.   Run from project root:   streamlit run src/web_app/app.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from src.data.portfolio import analyze_portfolio
from src.utils.guardrails import add_disclaimer, strip_disclaimer
from src.workflow.graph import ask, build_graph, close_checkpointer, thread_id_for_user

st.set_page_config(page_title="AI Finance Assistant", page_icon="💹", layout="wide")
st.title("💹 AI Finance Assistant")
st.caption("Educational only - not financial, investment, or tax advice.")

st.markdown(
    """<style>
    [data-testid="stMetric"] { background: rgba(120,130,160,.10); border: 1px solid rgba(120,130,160,.25);
        border-radius: 12px; padding: 14px 18px; }
    [data-testid="stMetricValue"] { color: #1f9d6b; }
    [data-testid="stChatMessage"] { border-radius: 14px; padding: .75rem 1rem; margin-bottom: .5rem;
        background: rgba(120,130,160,.08); }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
    [data-testid="stSidebar"] h2 { color: #1f9d6b; }
    div[role="radiogroup"] label { border: 1px solid rgba(120,130,160,.3); border-radius: 999px; padding: 2px 14px; }
    </style>""",
    unsafe_allow_html=True,
)


def release_graph(graph):
    close_checkpointer(graph.checkpointer)


@st.cache_resource(on_release=release_graph)
def get_graph():
    return build_graph()


@st.cache_data(ttl=60)
def get_portfolio_analysis(holdings: list[dict], refresh_version: int) -> dict:
    return analyze_portfolio(holdings)


if not st.user.is_logged_in:
    st.info("Please sign in with Google to continue.")
    st.button("Sign in with Google", icon=":material/login:", on_click=st.login, args=("google",))
    st.stop()

if not st.user.get("email_verified", False) or not st.user.get("email"):
    st.error("Your Google account email is not verified.")
    st.button("Sign out", on_click=st.logout)
    st.stop()

username = st.user.email.strip().lower()


with st.sidebar:
    st.write(f"Signed in as **{st.user.get('name') or username}**")
    st.caption(username)
    st.button("Sign out", on_click=st.logout)
    st.header("Portfolio (optional)")
    df = st.data_editor(
        pd.DataFrame({"ticker": ["AAPL", "VTI"], "shares": [10.0, 25.0], "cost_basis": [150.0, 200.0]}),
        num_rows="dynamic",
        key="portfolio_editor",
    )
    share = st.checkbox("Enable portfolio analysis and share with the assistant")

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

view = st.radio(
    "View", ["💬 Chat", "📈 Portfolio", "📊 Agent Metrics"],
    horizontal=True, label_visibility="collapsed",
)
in_chat = view == "💬 Chat"

if in_chat and username and (prompt := st.chat_input("Ask about investing, your goals, the markets, taxes...")):
    st.session_state.history.append({"role": "user", "content": prompt})
    portfolio = df.dropna(subset=["ticker", "shares"]).to_dict("records") if share else []
    started = time.perf_counter()
    try:
        with st.spinner("Thinking..."):
            out = ask(get_graph(), prompt, thread_id, portfolio, portfolio_shared=share)
        st.session_state.history.append({
            "role": "assistant", "content": out["messages"][-1].content,
            "agent": out["active_agent"], "sources": out.get("sources", []),
            "latency": time.perf_counter() - started,
        })
    except Exception as exc:
        st.session_state.history.append({"role": "assistant", "content": f"Error: {exc}", "error": True})

PAGE_SIZE = 10
if not in_chat or st.session_state.get("chat_user") != username:
    st.session_state.chat_limit = PAGE_SIZE  # back to the latest page when returning to chat
    st.session_state.chat_user = username

if in_chat:
    if not username:
        st.info("Sign in to load or start your conversation.")
    else:
        history = st.session_state.history
        shown = history[-st.session_state.chat_limit:]
        with st.container(height=520):  # scrollable chat frame; title stays fixed above
            if len(history) > len(shown) and st.button("⬆️ Show earlier messages"):
                st.session_state.chat_limit += PAGE_SIZE
                st.rerun()
            for m in shown:
                with st.chat_message(m["role"]):
                    st.markdown(add_disclaimer(m["content"]) if m.get("agent") else m["content"])
                    if m.get("agent"):
                        sources = list(dict.fromkeys(m.get("sources", [])))
                        st.caption(f"Agent: {m['agent']}" + (f" | Sources: {', '.join(sources)}" if sources else ""))

elif view == "📈 Portfolio":
    st.header("Portfolio analysis")
    if not share:
        st.info(
            "Portfolio analysis is disabled. Turn on **Enable portfolio analysis and share with "
            "the assistant** in the sidebar to fetch prices and build the dashboard."
        )
    else:
        st.caption(
            "Yahoo Finance quotes may be delayed and are cached for up to 60 seconds."
        )
        if "portfolio_refresh_version" not in st.session_state:
            st.session_state.portfolio_refresh_version = 0
        if st.button("Refresh prices", icon=":material/refresh:"):
            st.session_state.portfolio_refresh_version += 1

        portfolio_holdings = df.dropna(subset=["ticker", "shares"]).to_dict("records")
        if not portfolio_holdings:
            st.info("Add holdings in the sidebar to see portfolio analysis.")
        else:
            with st.spinner("Fetching portfolio prices and sector data..."):
                analysis = get_portfolio_analysis(
                    portfolio_holdings, st.session_state.portfolio_refresh_version
                )

            if not analysis["rows"]:
                st.warning("No valid holdings could be priced. Check the tickers and try refreshing.")
            else:
                metric_row = st.columns(4)
                metric_row[0].metric("Portfolio value", f"${analysis['total_value']:,.2f}")
                metric_row[1].metric("Priced positions", len(analysis["rows"]))
                metric_row[2].metric("Largest position", f"{analysis['top_weight']:.1%}")
                metric_row[3].metric("Effective holdings", f"{analysis['effective_holdings']:.1f}")

                allocation_col, sector_col = st.columns(2)
                with allocation_col:
                    st.subheader("Value by holding")
                    allocation = pd.DataFrame(
                        [{"Ticker": row["ticker"], "Market value": row["value"]}
                         for row in analysis["rows"]]
                    ).sort_values("Market value", ascending=False)
                    st.bar_chart(allocation, x="Ticker", y="Market value")
                with sector_col:
                    st.subheader("Sector allocation")
                    sectors = pd.DataFrame(
                        [{"Sector": sector, "Allocation (%)": weight * 100}
                         for sector, weight in sorted(
                             analysis["sectors"].items(), key=lambda item: -item[1]
                         )]
                    )
                    st.bar_chart(sectors, x="Sector", y="Allocation (%)")

                st.subheader("Holdings breakdown")
                holdings_table = pd.DataFrame([
                    {
                        "Ticker": row["ticker"],
                        "Shares": row["shares"],
                        "Price": f"${row['price']:,.2f}",
                        "Market value": f"${row['value']:,.2f}",
                        "Allocation": f"{row['weight']:.1%}",
                        "Sector": row["sector"],
                        "Gain/loss": f"{row['gain_pct']:+.1f}%" if row["gain_pct"] is not None else "N/A",
                    }
                    for row in sorted(analysis["rows"], key=lambda item: -item["weight"])
                ])
                st.dataframe(holdings_table, hide_index=True)
                if analysis["skipped"]:
                    st.warning("Could not retrieve prices for: " + ", ".join(analysis["skipped"]))

else:
    replies = [m for m in st.session_state.get("history", []) if m.get("agent")]
    if not replies:
        st.info("No agent activity yet. Ask a question to see per-agent metrics.")
    else:
        rows = []
        for name in sorted({m["agent"] for m in replies}):
            items = [m for m in replies if m["agent"] == name]
            lat = [m["latency"] for m in items if "latency" in m]
            rows.append({
                "Agent": name,
                "Responses": len(items),
                "Share %": round(100 * len(items) / len(replies), 1),
                "Avg latency (s)": round(sum(lat) / len(lat), 2) if lat else None,
                "Max latency (s)": round(max(lat), 2) if lat else None,
                "Sources cited": sum(len(m.get("sources", [])) for m in items),
                "Avg answer length (chars)": round(sum(len(m["content"]) for m in items) / len(items)),
            })
        stats = pd.DataFrame(rows)
        top = stats.loc[stats["Responses"].idxmax()]
        c1, c2, c3 = st.columns(3)
        c1.metric("Total responses", len(replies))
        c2.metric("Agents used", len(stats))
        c3.metric("Most used agent", top["Agent"])
        st.dataframe(stats, hide_index=True, use_container_width=True)
        st.bar_chart(stats.set_index("Agent")["Responses"])
        st.caption("Latency is measured for this browser session only; earlier history shows counts only.")
