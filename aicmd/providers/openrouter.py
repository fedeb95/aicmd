import os
import httpx
from .base import Provider
from .. import config as cfg_mod

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

class OpenRouterProvider(Provider):
    def describe_image(self, image_path: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60) -> str:
        """OpenRouter does not support image description in this CLI.
        Raises a clear error to inform the user.
        """
        raise NotImplementedError("Image description is not supported for OpenRouter provider")
    def __init__(self):
        cfg = cfg_mod.load()
        self.api_key = cfg.get("openrouter_key")
        if not self.api_key:
            raise RuntimeError("OpenRouter API key not configured (AI_OPENROUTER_KEY or ~/.aicmd.yaml)")
        self.default_model = cfg.get("model", "mistralai/mistral-7b-instruct")
        self.client = httpx.Client()

    def summarize(self, text: str, *, model: str | None = None, max_tokens: int = 256, timeout: int = 60, stream_callback = None) -> str:
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
        try:
            choice = data["choices"][0]
            message = choice["message"] if isinstance(choice, dict) else {}
            summary = (message.get("content", "") if isinstance(message, dict) else message or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected response from OpenRouter: {data}"
            ) from exc
        if stream_callback:
            stream_callback(summary)
        return summary

    def rewrite(self, text: str, style: str, *, model: str | None = None, max_tokens: int = 256, timeout: int = 60, stream_callback = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": f"You are a helpful assistant. Rewrite the user's text following this style or instruction: {style}. Do not add introductory text or meta-commentary, just output the rewritten text directly."},
                {"role": "user", "content": text},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        resp = self.client.post(OPENROUTER_ENDPOINT, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        try:
            choice = data["choices"][0]
            message = choice["message"] if isinstance(choice, dict) else {}
            rewritten = (message.get("content", "") if isinstance(message, dict) else message or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected response from OpenRouter: {data}"
            ) from exc
        if stream_callback:
            stream_callback(rewritten)
        return rewritten

