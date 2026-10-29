"""Model-agnostic factories. Swap models/providers via config.yaml or env vars - no code changes."""
import os
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings

from src.core.config import agent_cfg, load_config

_LLM_KEYS = ("provider", "model", "temperature", "max_tokens")


def get_llm(agent: str | None = None):
    """Resolution order: config.yaml `llm` < env (LLM_PROVIDER / LLM_MODEL) < agents.<agent> overrides."""
    cfg = dict(load_config()["llm"])
    if os.getenv("LLM_PROVIDER"):
        cfg["provider"] = os.environ["LLM_PROVIDER"]
    if os.getenv("LLM_MODEL"):
        cfg["model"] = os.environ["LLM_MODEL"]
    if agent:
        cfg.update({k: v for k, v in agent_cfg(agent).items() if k in _LLM_KEYS})
    return _build_llm(cfg["provider"], cfg["model"], cfg.get("temperature"), cfg.get("max_tokens"))


@lru_cache(maxsize=None)
def _build_llm(provider: str, model: str, temperature, max_tokens):
    kwargs = {k: v for k, v in {"temperature": temperature, "max_tokens": max_tokens}.items() if v is not None}
    return init_chat_model(model=model, model_provider=provider, **kwargs)


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    e = load_config()["embeddings"]
    return init_embeddings(f"{e['provider']}:{e['model']}")
