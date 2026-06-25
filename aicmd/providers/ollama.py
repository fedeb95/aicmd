import os
import json
import httpx
import sys
from .base import Provider
from .. import config as cfg_mod

DEFAULT_OLLAMA_URL = "http://localhost:11434"

class OllamaProvider(Provider):
    def __init__(self):
        cfg = cfg_mod.load()
        self.base_url = cfg.get("ollama_url", DEFAULT_OLLAMA_URL).rstrip('/')
        self.default_model = cfg.get("model", "qwen2.5:0.5b")
        self.client = httpx.Client()

    def summarize(self, text: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60) -> str:
        """Generate a summary using Ollama with streaming output.

        If the specified model is not available, attempt to pull it and retry.
        Logging related to model pulling is written to ``stderr``.
        The generated text is streamed to standard output as it arrives.
        """
        # Load an optional prompt template from configuration; fall back to default if not set
        cfg = cfg_mod.load()
        prompt_template = cfg.get("ollama_prompt_template",
            "Summarize the following text in ONE concise sentence, preserving key facts and proper nouns. Do not add explanations or extra information.\n\n{{text}}")
        # Render the template (simple replacement)
        prompt = prompt_template.replace("{{text}}", text)
        # Determine max_tokens: use argument, else configurable default, else a safe small limit
        cfg_local = cfg_mod.load()
        default_max = cfg_local.get("ollama_max_tokens", 80)
        effective_max = max_tokens if max_tokens is not None else default_max
        payload = {
            "model": model or self.default_model,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.1,
            "max_tokens": effective_max,
        }
        try:
            with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=timeout) as resp:
                resp.raise_for_status()
                # Stream each chunk's content to stdout
                prev_response = ""
                for line in resp.iter_text():
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            # Print the response chunk as received
                            print(obj["response"], end="", flush=True)
                            prev_response += obj["response"]
                    except json.JSONDecodeError:
                        print(line, end="", flush=True)
                # The streamed output has been printed; return empty string
                return ""
        except httpx.HTTPError as e:
            # If the model is not found (typically a 404), attempt to pull it
            if getattr(e.response, "status_code", None) == 404:
                model_name = payload["model"]
                print(f"Ollama model '{model_name}' not found. Pulling model...", file=sys.stderr)
                pull_resp = self.client.post(f"{self.base_url}/api/pull", json={"name": model_name})
                pull_resp.raise_for_status()
                # Retry the original request after pulling
                with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=timeout) as resp:
                    resp.raise_for_status()
                    # Reset tracking for retry
                    prev_response = ""
                    for line in resp.iter_text():
                        try:
                            obj = json.loads(line)
                            if "response" in obj:
                                # Determine the new portion of the response
                                if obj["response"].startswith(prev_response):
                                    new_part = obj["response"][len(prev_response):]
                                else:
                                    # Fallback: treat as fresh fragment
                                    new_part = obj["response"]
                                if new_part:
                                    print(new_part, end="", flush=True)
                                prev_response = obj["response"]
                        except json.JSONDecodeError:
                            print(line, end="", flush=True)
                    data = {"response": prev_response}
            else:
                raise
        # Return the full generated response for callers that need it
        return data.get("response", "").strip()
