import os
import httpx
from .base import Provider
from .. import config as cfg_mod

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

class OpenRouterProvider(Provider):
    def __init__(self):
        cfg = cfg_mod.load()
        self.api_key = cfg.get("openrouter_key")
        if not self.api_key:
            raise RuntimeError("OpenRouter API key not configured (AI_OPENROUTER_KEY or ~/.aicmd.yaml)")
        self.default_model = cfg.get("model", "mistralai/mistral-7b-instruct")
        self.client = httpx.Client()

    def summarize(self, text: str, *, model: str | None = None, max_tokens: int = 256, timeout: int = 60) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": "You are a concise summarizer. Produce a short summary without extra explanation."},
                {"role": "user", "content": f"Summarize the following text:\n\n{text}"},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        resp = self.client.post(OPENROUTER_ENDPOINT, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # OpenRouter follows OpenAI schema: choices[0].message.content
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
