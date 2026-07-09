import os
import json
import httpx
import sys
from .base import Provider
from .. import config as cfg_mod

DEFAULT_OLLAMA_URL = "http://localhost:8080"

class OllamaProvider(Provider):
    def describe_image(self, image_path: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60) -> str:
        """Describe an image.

        The image is read and base64‑encoded, then sent to Ollama with a prompt that asks for a concise description.
        """
        import base64
        # Load image and encode
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        # Prompt for description
        cfg_local = cfg_mod.load()
        prompt_template = cfg_local.get("ollama_image_prompt_template",
            "Describe the image in ONE concise sentence.")

        # Determine model (default to moondream if not overridden)
        # Model for image description (default Moondream) can be configured separately
        default_image_model = cfg_local.get("ollama_describe_model", "ahmadwaqar/smolvlm2-256m-video:q8_0")
        # Force use of the image description model unless the caller explicitly overrides
        effective_model = model if model is not None else default_image_model
        # Token limit for description, configurable separately
        default_max = cfg_local.get("ollama_describe_max_tokens", 80)
        effective_max = max_tokens if max_tokens is not None else default_max
        payload = {
            "model": effective_model,
            "prompt": prompt_template,
            "stream": False,
            "temperature": 0.1,
            "max_tokens": effective_max,
            "images": [img_b64],
        }
        try:
            resp = self.client.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            description = data.get("response", "").strip()
            # Log the full response for debugging
            return description
        except httpx.HTTPError as e:
            # If the model is not found, pull it and retry (same logic as summarize)
            if getattr(e.response, "status_code", None) == 404:
                model_name = payload["model"]
                print(f"Ollama model '{model_name}' not found. Pulling model...", file=sys.stderr)
                pull_resp = self.client.post(f"{self.base_url}/api/pull", json={"name": model_name})
                pull_resp.raise_for_status()
                # Retry the generate request after pulling
                resp = self.client.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                description = data.get("response", "").strip()
                print("DEBUG describe_image response after pull:", data, file=sys.stderr)
                print(description, end="", flush=True)
                return description
            else:
                raise
    def __init__(self):
        cfg = cfg_mod.load()
        self.base_url = cfg.get("ollama_url", DEFAULT_OLLAMA_URL).rstrip('/')
        self.client = httpx.Client()

    def summarize(self, text: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60, stream_callback = None) -> str:
        """Generate a summary using Ollama with streaming output.

        If the specified model is not available, attempt to pull it and retry.
        Logging related to model pulling is written to ``stderr``.
        """
        # Load an optional prompt template from configuration; fall back to default if not set
        cfg = cfg_mod.load()

        default_summarize_model = cfg.get("ollama_summarize_model", "qwen2.5:0.5b-instruct")
        # Force use of the image description model unless the caller explicitly overrides
        effective_model = model if model is not None else default_summarize_model 

        prompt_template = cfg.get("ollama_prompt_template",
            "Summarize the following text in ONE concise sentence, preserving key facts and proper nouns. Do not add explanations or extra information.\n\n{{text}}")
        # Render the template (simple replacement)
        prompt = prompt_template.replace("{{text}}", text)
        # Determine max_tokens: use argument, else configurable default, else a safe small limit
        cfg_local = cfg_mod.load()
        default_max = cfg_local.get("ollama_max_tokens", 80)
        effective_max = max_tokens if max_tokens is not None else default_max
        payload = {
            "model": effective_model,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.1,
        }
        try:
            with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=timeout) as resp:
                resp.raise_for_status()
                prev_response = ""
                for line in resp.iter_text():
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            chunk = obj["response"]
                            if stream_callback:
                                stream_callback(chunk)
                            prev_response += chunk
                    except json.JSONDecodeError:
                        if stream_callback:
                            stream_callback(line)
                return prev_response.strip()
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
                    prev_response = ""
                    for line in resp.iter_text():
                        try:
                            obj = json.loads(line)
                            if "response" in obj:
                                # Determine the new portion of the response
                                if obj["response"].startswith(prev_response):
                                    new_part = obj["response"][len(prev_response):]
                                else:
                                    new_part = obj["response"]
                                if new_part:
                                    if stream_callback:
                                        stream_callback(new_part)
                                prev_response = obj["response"]
                        except json.JSONDecodeError:
                            if stream_callback:
                                stream_callback(line)
                    return prev_response.strip()
            else:
                raise

    def rewrite(self, text: str, style: str, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60, stream_callback = None) -> str:
        """Rewrite text in a given style using Ollama."""
        cfg = cfg_mod.load()
        default_summarize_model = cfg.get("ollama_summarize_model", "qwen2.5:0.5b-instruct")
        effective_model = model if model is not None else default_summarize_model

        # Default rewrite prompt template
        prompt_template = cfg.get("ollama_rewrite_prompt_template",
            "[Instruction]\nRewrite the text below to match this style or instruction: {{style}}\n\n[Constraints]\n- Output ONLY the final rewritten text.\n- Do NOT include any introductory words, conversational filler (such as \"Okay\", \"Sure\", \"Here is\"), or quotes around the output.\n- Do NOT explain your changes.\n\n[Text to Rewrite]\n{{text}}\n\n[Rewritten Text]\n")
        prompt = prompt_template.replace("{{style}}", style).replace("{{text}}", text)
        
        cfg_local = cfg_mod.load()
        default_max = cfg_local.get("ollama_max_tokens", 256)
        effective_max = max_tokens if max_tokens is not None else default_max
        payload = {
            "model": effective_model,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.3,
        }
        try:
            with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=timeout) as resp:
                resp.raise_for_status()
                prev_response = ""
                for line in resp.iter_text():
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            chunk = obj["response"]
                            if stream_callback:
                                stream_callback(chunk)
                            prev_response += chunk
                    except json.JSONDecodeError:
                        if stream_callback:
                            stream_callback(line)
                return prev_response.strip()
        except httpx.HTTPError as e:
            if getattr(e.response, "status_code", None) == 404:
                model_name = payload["model"]
                print(f"Ollama model '{model_name}' not found. Pulling model...", file=sys.stderr)
                pull_resp = self.client.post(f"{self.base_url}/api/pull", json={"name": model_name})
                pull_resp.raise_for_status()
                with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=timeout) as resp:
                    resp.raise_for_status()
                    prev_response = ""
                    for line in resp.iter_text():
                        try:
                            obj = json.loads(line)
                            if "response" in obj:
                                if obj["response"].startswith(prev_response):
                                    new_part = obj["response"][len(prev_response):]
                                else:
                                    new_part = obj["response"]
                                if new_part:
                                    if stream_callback:
                                        stream_callback(new_part)
                                prev_response = obj["response"]
                        except json.JSONDecodeError:
                            if stream_callback:
                                key = line
                                stream_callback(key)
                    return prev_response.strip()
            else:
                raise

    def chat(self, messages: list, *, model: str | None = None, max_tokens: int | None = None, timeout: int = 60, stream_callback = None) -> str:
        """Simple chat support by composing messages into a single prompt and calling Ollama generate."""
        cfg = cfg_mod.load()
        default_model = cfg.get("ollama_summarize_model", "qwen2.5:0.5b-instruct")
        effective_model = model if model is not None else default_model

        # Build prompt: combine system messages at top, then interleave user/assistant messages
        system_parts = [m['content'] for m in messages if m.get('role') == 'system']
        conv_parts = []
        for m in messages:
            role = m.get('role')
            if role == 'system':
                continue
            content = m.get('content', '')
            if role == 'user':
                conv_parts.append(f"User: {content}")
            elif role == 'assistant':
                conv_parts.append(f"Assistant: {content}")
            else:
                conv_parts.append(f"{role.capitalize()}: {content}")
        prompt = "\n\n".join(system_parts + conv_parts + ["Assistant:"])

        payload = {
            "model": effective_model,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.2,
        }
        try:
            with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=timeout) as resp:
                resp.raise_for_status()
                prev_response = ""
                for line in resp.iter_text():
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            chunk = obj["response"]
                            if stream_callback:
                                stream_callback(chunk)
                            prev_response += chunk
                    except json.JSONDecodeError:
                        if stream_callback:
                            stream_callback(line)
                return prev_response.strip()
        except httpx.HTTPError as e:
            if getattr(e.response, "status_code", None) == 404:
                model_name = payload["model"]
                print(f"Ollama model '{model_name}' not found. Pulling model...", file=sys.stderr)
                pull_resp = self.client.post(f"{self.base_url}/api/pull", json={"name": model_name})
                pull_resp.raise_for_status()
                with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=timeout) as resp:
                    resp.raise_for_status()
                    prev_response = ""
                    for line in resp.iter_text():
                        try:
                            obj = json.loads(line)
                            if "response" in obj:
                                if obj["response"].startswith(prev_response):
                                    new_part = obj["response"][len(prev_response):]
                                else:
                                    new_part = obj["response"]
                                if new_part:
                                    if stream_callback:
                                        stream_callback(new_part)
                                prev_response = obj["response"]
                        except json.JSONDecodeError:
                            if stream_callback:
                                key = line
                                stream_callback(key)
                    return prev_response.strip()
            else:
                raise
