import sys
from pathlib import Path
from typing import Optional, Callable
from . import config, providers

def summarize_text(
    text: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Summarize text using the configured or explicitly specified provider."""
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    
    # Use the model string directly (do not look it up as a config key)
    resolved_model = model or None
    
    return prov.summarize(
        text,
        model=resolved_model,
        max_tokens=max_tokens,
        timeout=effective_timeout,
        stream_callback=stream_callback,
    )

def describe_image(
    image_path: Path,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
) -> str:
    """Describe an image using the configured or explicitly specified provider."""
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    if not hasattr(prov, "describe_image"):
        raise NotImplementedError(f"Selected provider '{prov_name}' does not support image description")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    
    # Use the model string directly (do not look it up as a config key)
    resolved_model = model or None

    return prov.describe_image(
        str(image_path),
        max_tokens=max_tokens,
        timeout=effective_timeout,
        model=resolved_model,
    )

def rewrite_text(
    text: str,
    style: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Rewrite text in a given style using the configured or explicitly specified provider."""
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)

    # Use the model string directly (do not look it up as a config key)
    resolved_model = model or None

    return prov.rewrite(
        text,
        style,
        model=resolved_model,
        max_tokens=max_tokens,
        timeout=effective_timeout,
        stream_callback=stream_callback,
    )

