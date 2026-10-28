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
    from src.workflow.graph import build_graph
    nodes = set(build_graph().get_graph().nodes)
    assert {"router", "finance_qa", "portfolio", "market", "goal_planning", "news", "tax"} <= nodes
