from src.core.config import load_config
from src.core.llm_factory import get_llm


def test_config_has_required_sections():
    cfg = load_config()
    assert {"llm", "embeddings", "pinecone", "rag", "agents", "data"} <= cfg.keys()


def test_model_swap_via_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    assert get_llm("finance_qa").model_name == "gpt-4o"


def test_graph_has_all_nodes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    from src.workflow.graph import build_graph, close_checkpointer

    graph = build_graph()
    try:
        nodes = set(graph.get_graph().nodes)
        assert {
            "router",
            "finance_qa_agent",
            "portfolio_agent",
            "market_agent",
            "goal_planning_agent",
            "news_agent",
            "tax_agent",
        } <= nodes
    finally:
        close_checkpointer(graph.checkpointer)


def test_close_checkpointer_closes_owned_connection():
    from types import SimpleNamespace

    from src.workflow.graph import close_checkpointer

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    conn = FakeConnection()
    close_checkpointer(SimpleNamespace(conn=conn))
    assert conn.closed


def test_thread_id_is_stable_for_username():
    from src.workflow.graph import thread_id_for_user

    assert thread_id_for_user(" Alice ") == "user:alice"
    assert thread_id_for_user("ALICE") == thread_id_for_user("alice")


def test_thread_id_rejects_empty_username():
    import pytest

    from src.workflow.graph import thread_id_for_user

    with pytest.raises(ValueError, match="Username must not be empty"):
        thread_id_for_user("   ")


def test_ask_adds_langsmith_trace_context():
    from src.workflow.graph import ask

    class FakeGraph:
        def invoke(self, payload, config):
            self.payload = payload
            self.config = config
            return {"ok": True}

    graph = FakeGraph()
    result = ask(graph, "Explain index funds", "user:alice", portfolio=[])

    assert result == {"ok": True}
    assert graph.config["run_name"] == "finance-assistant-chat"
    assert graph.config["tags"] == ["ai-finance-assistant", "chat"]
    assert graph.config["metadata"] == {"application": "ai-finance-assistant"}
    assert graph.config["configurable"]["thread_id"] == "user:alice"
    assert graph.payload["portfolio"] == []


def test_ask_explicitly_enables_langsmith_tracing(monkeypatch):
    from contextlib import nullcontext

    import langchain_core.tracers.context as tracer_context
    import langsmith

    from src.workflow.graph import ask

    class FakeGraph:
        def invoke(self, payload, config):
            return {"ok": True}

    calls = {}

    def fake_tracing_context(**kwargs):
        calls.update(kwargs)
        return nullcontext()

    class FakeClient:
        def __init__(self, *, api_key):
            calls["api_key"] = api_key

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-langsmith-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
    monkeypatch.setattr(tracer_context, "tracing_v2_enabled", fake_tracing_context)
    monkeypatch.setattr(langsmith, "Client", FakeClient)

    assert ask(FakeGraph(), "Explain index funds") == {"ok": True}
    assert calls["api_key"] == "test-langsmith-key"
    assert calls["project_name"] == "test-project"
    assert calls["tags"] == ["ai-finance-assistant", "chat"]


def test_ask_rejects_enabled_langsmith_tracing_without_api_key(monkeypatch):
    import pytest
    from src.workflow.graph import ask

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY is not set"):
        ask(object(), "Explain index funds")


def test_yfinance_dataframe_inplace_warning_filter_is_narrow():
    import warnings

    from pandas.errors import Pandas4Warning

    from src.data.yfinance_compat import ignore_yfinance_dataframe_inplace_warning

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with ignore_yfinance_dataframe_inplace_warning():
            warnings.warn_explicit(
                "The inplace keyword in DataFrame.sort_index is deprecated.",
                Pandas4Warning,
                filename="yfinance/utils.py",
                lineno=1,
                module="yfinance.utils",
            )
            warnings.warn_explicit(
                "The inplace keyword in DataFrame.set_index is deprecated.",
                Pandas4Warning,
                filename="yfinance/utils.py",
                lineno=1,
                module="yfinance.utils",
            )
            warnings.warn_explicit(
                "An unrelated warning.",
                UserWarning,
                filename="yfinance/utils.py",
                lineno=1,
                module="yfinance.utils",
            )

    assert len(caught) == 1
    assert str(caught[0].message) == "An unrelated warning."
