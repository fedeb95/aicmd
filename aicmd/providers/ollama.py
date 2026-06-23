import os
import json
import httpx
from .base import Provider
from .. import config as cfg_mod

DEFAULT_OLLAMA_URL = "http://localhost:11434"

class OllamaProvider(Provider):
    def __init__(self):
        cfg = cfg_mod.load()
        self.base_url = cfg.get("ollama_url", DEFAULT_OLLAMA_URL).rstrip('/')
        self.default_model = cfg.get("model", "llama3:8b")
        self.client = httpx.Client()

    def summarize(self, text: str, *, model: str | None = None, max_tokens: int = 256, timeout: int = 60) -> str:
        payload = {
            "model": model or self.default_model,
            "prompt": f"Summarize the following text:\n\n{text}\n\nSummary:",
            "stream": False,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        resp = self.client.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns the generated text in the "response" field
        return data.get("response", "").strip()
