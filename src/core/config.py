"""Central config loader: config.yaml + .env. Everything else reads settings from here."""
import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def load_config() -> dict:
    path = Path(os.getenv("FINANCE_AI_CONFIG", ROOT / "config.yaml"))
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def agent_cfg(name: str) -> dict:
    return load_config().get("agents", {}).get(name, {}) or {}
