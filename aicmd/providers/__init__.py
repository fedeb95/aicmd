from .base import Provider
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider

def get_provider(name: str) -> Provider | None:
    name = (name or "").lower()
    if name == "ollama":
        return OllamaProvider()
    if name == "openrouter":
        return OpenRouterProvider()
    return None
