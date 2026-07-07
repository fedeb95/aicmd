import os
import yaml
from pathlib import Path

# Backwards-compatible: prefer ~/.aicmd.yaml, but also support ~/.aicmd/config.yaml
LEGACY_PATH = Path.home() / ".aicmd.yaml"
CONFIG_DIR = Path.home() / ".aicmd"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

def load() -> dict:
    """Load configuration from YAML file and environment variables.
    Environment variables take precedence over file values.
    """
    cfg = {}
    if LEGACY_PATH.is_file():
        path = LEGACY_PATH
    elif CONFIG_PATH.is_file():
        path = CONFIG_PATH
    else:
        path = None

    if path:
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        cfg = loaded if isinstance(loaded, dict) else {}

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
