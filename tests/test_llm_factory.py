from src.core import llm_factory


def test_llm_configuration_precedence_and_provider_options(monkeypatch):
    received = []
    monkeypatch.setattr(llm_factory, "load_config", lambda: {
        "llm": {"provider": "openai", "model": "default", "temperature": 0.1, "max_tokens": 200}
    })
    monkeypatch.setattr(llm_factory, "agent_cfg", lambda name: {
        "provider": "anthropic", "model": "agent-model", "temperature": 0.4,
        "max_tokens": 500, "rag_namespaces": ["tax"],
    })
    monkeypatch.setattr(
        llm_factory, "_build_llm",
        lambda *args: received.append(args) or "model",
    )
    monkeypatch.setenv("LLM_PROVIDER", "google_genai")
    monkeypatch.setenv("LLM_MODEL", "environment-model")

    assert llm_factory.get_llm("tax_agent") == "model"
    assert received == [("anthropic", "agent-model", 0.4, 500)]


def test_embeddings_use_provider_timeout_options(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_factory, "load_config", lambda: {
        "embeddings": {"provider": "openai", "model": "text-embedding-test"}
    })
    monkeypatch.setattr(
        llm_factory, "init_embeddings",
        lambda model, **kwargs: calls.append((model, kwargs)) or object(),
    )
    llm_factory.get_embeddings.cache_clear()

    try:
        llm_factory.get_embeddings()
        assert calls == [("openai:text-embedding-test", {"timeout": 30, "max_retries": 2})]
    finally:
        llm_factory.get_embeddings.cache_clear()
