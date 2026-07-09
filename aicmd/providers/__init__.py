from .base import Provider
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider
from .llamaserver import LlamaServerProvider

def get_provider(name: str) -> Provider | None:
    name = (name or "").lower()
    if name == "ollama":
        return OllamaProvider()
    if name == "openrouter":
        return OpenRouterProvider()
    if name == "llamaserver" or name == "llama-server" or name == "llama.cpp":
        return LlamaServerProvider()
    return None
