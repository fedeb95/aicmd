import os
import json
import httpx
import sys
from .base import Provider
from .. import config as cfg_mod

DEFAULT_LLAMASERVER_URL = "http://127.0.0.1:8081"

class LlamaServerProvider(Provider):
    """Provider for llama.cpp's llama-server using OpenAI-compatible API."""

    def __init__(self):
        cfg = cfg_mod.load()
        self.base_url = cfg.get("llamaserver_url", DEFAULT_LLAMASERVER_URL).rstrip('/')
        self.client = httpx.Client()

    def _chat_completion_request(self, messages: list, model: str | None, max_tokens: int, temperature: float, timeout: int, stream_callback=None) -> str:
        """Make a chat completion request to llama-server and handle streaming.

        Retry automaticamente in caso di ConnectError per gestire il tempo di
        avvio/warmup del modello (fino a max_wait secondi).
        """
        import time

        max_wait   = min(timeout, 60)   # aspetta al massimo 60s o il timeout impostato
        wait       = 1.0
        elapsed    = 0.0

        while True:
            try:
                return self._attempt_request(messages, model, max_tokens, temperature, timeout, stream_callback)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if elapsed >= max_wait:
                    raise RuntimeError(
                        f"llama-server non raggiungibile su {self.base_url} dopo {int(elapsed)}s — "
                        "assicurati che sia avviato e che il modello sia caricato."
                    )
                time.sleep(wait)
                elapsed += wait
                wait = min(wait * 1.5, 8.0)

    def _attempt_request(self, messages: list, model: str | None, max_tokens: int, temperature: float, timeout: int, stream_callback=None) -> str:
        """Singola tentativo di chiamata HTTP a llama-server."""
        payload = {
            "model": model or "default",
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with self.client.stream("POST", f"{self.base_url}/v1/chat/completions", json=payload, timeout=timeout) as resp:
                resp.raise_for_status()
                prev_response = ""
                for line in resp.iter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    # SSE format: "data: {json}"
                    if line.startswith("data: "):
                        line = line[6:]
                    if line == "[DONE]":
                        break
                    try:
                        obj = json.loads(line)
                        if "choices" in obj and len(obj["choices"]) > 0:
                            choice = obj["choices"][0]
                            delta = choice.get("delta", {})
                            if "content" in delta:
                                chunk = delta["content"]
                                if chunk is None:
                                    continue
                                if stream_callback:
                                    stream_callback(chunk)
                                prev_response += chunk
                    except json.JSONDecodeError:
                        pass
                return prev_response.strip()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Rilancia senza modifiche: il loop in _chat_completion_request gestisce i retry
            raise
        except httpx.TimeoutException:
            raise RuntimeError(
                f"llama-server ha impiegato troppo tempo a rispondere ({timeout}s). "
                "Prova ad aumentare il timeout o ad usare un modello più leggero."
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"llama-server ha risposto con errore HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
        except httpx.HTTPError as e:
            raise RuntimeError(f"Errore di rete con llama-server: {e}")

    def summarize(self, text: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60, stream_callback = None) -> str:
        """Generate a summary using llama-server with streaming output."""
        cfg = cfg_mod.load()
        default_model = cfg.get("llamaserver_summarize_model", "qwen2.5:0.5b-instruct")
        effective_model = model if model is not None else default_model

        prompt_template = cfg.get("llamaserver_prompt_template",
            "Summarize the following text in ONE concise sentence, preserving key facts and proper nouns. Do not add explanations or extra information.\n\n{{text}}")
        prompt = prompt_template.replace("{{text}}", text)

        cfg_local = cfg_mod.load()
        default_max = cfg_local.get("llamaserver_max_tokens", 80)
        effective_max = max_tokens if max_tokens is not None else default_max

        messages = [
            {"role": "system", "content": "You are a helpful assistant that creates concise summaries."},
            {"role": "user", "content": prompt}
        ]

        return self._chat_completion_request(messages, effective_model, effective_max, 0.1, timeout, stream_callback)

    def describe_image(self, image_path: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60) -> str:
        """Describe an image.

        Note: Image support depends on the llama-server model capabilities and configuration.
        The image is read and base64-encoded, then sent with vision-capable model.
        """
        import base64
        cfg = cfg_mod.load()

        # Load image and encode
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Determine media type from file extension
        ext = image_path.lower().split('.')[-1]
        media_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
        }
        media_type = media_type_map.get(ext, 'image/jpeg')

        prompt_template = cfg.get("llamaserver_image_prompt_template",
            "Describe the image in ONE concise sentence.")

        default_image_model = cfg.get("llamaserver_describe_model", "ahmadwaqar/smolvlm2-256m-video:q8_0")
        effective_model = model if model is not None else default_image_model

        default_max = cfg.get("llamaserver_describe_max_tokens", 80)
        effective_max = max_tokens if max_tokens is not None else default_max

        # Use vision-compatible message format with image URL
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_template},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_b64}"}}
                ]
            }
        ]

        return self._chat_completion_request(messages, effective_model, effective_max, 0.1, timeout)

    def rewrite(self, text: str, style: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60, stream_callback = None) -> str:
        """Rewrite text in a given style using llama-server."""
        cfg = cfg_mod.load()
        default_model = cfg.get("llamaserver_summarize_model", "qwen2.5:0.5b-instruct")
        effective_model = model if model is not None else default_model

        prompt_template = cfg.get("llamaserver_rewrite_prompt_template",
            "[Instruction]\nRewrite the text below to match this style or instruction: {{style}}\n\n[Constraints]\n- Output ONLY the final rewritten text.\n- Do NOT include any introductory words, conversational filler (such as \"Okay\", \"Sure\", \"Here is\"), or quotes around the output.\n- Do NOT explain your changes.\n\n[Text to Rewrite]\n{{text}}\n\n[Rewritten Text]\n")
        prompt = prompt_template.replace("{{style}}", style).replace("{{text}}", text)

        cfg_local = cfg_mod.load()
        default_max = cfg_local.get("llamaserver_max_tokens", 256)
        effective_max = max_tokens if max_tokens is not None else default_max

        messages = [
            {"role": "system", "content": "You are a helpful assistant that rewrites text according to specific styles or instructions."},
            {"role": "user", "content": prompt}
        ]

        return self._chat_completion_request(messages, effective_model, effective_max, 0.3, timeout, stream_callback)

    def chat(self, messages: list, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60, stream_callback = None) -> str:
        """Chat with the model using llama-server."""
        cfg = cfg_mod.load()
        default_model = cfg.get("llamaserver_summarize_model", "qwen2.5:0.5b-instruct")
        effective_model = model if model is not None else default_model

        cfg_local = cfg_mod.load()
        default_max = cfg_local.get("llamaserver_max_tokens", 512)
        effective_max = max_tokens if max_tokens is not None else default_max

        return self._chat_completion_request(messages, effective_model, effective_max, 0.2, timeout, stream_callback)
