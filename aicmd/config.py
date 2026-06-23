import os
import yaml
from pathlib import Path

DEFAULT_PATH = Path.home() / ".aicmd.yaml"

def load() -> dict:
    """Load configuration from YAML file and environment variables.
    Environment variables take precedence over file values.
    """
    cfg = {}
    if DEFAULT_PATH.is_file():
        with open(DEFAULT_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    # override with env vars if present
    env_map = {
        "provider": os.getenv("AI_PROVIDER"),
        "model": os.getenv("AI_MODEL"),
        "ollama_url": os.getenv("AI_OLLAMA_URL"),
        "openrouter_key": os.getenv("AI_OPENROUTER_KEY"),
    }
    for k, v in env_map.items():
        if v:
            cfg[k] = v
    return cfg
