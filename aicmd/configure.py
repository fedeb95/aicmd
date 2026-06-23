import json
import os
from pathlib import Path
import typer
import httpx
from . import config as cfg_mod

app = typer.Typer(help="Helper commands for configuring providers")

CONFIG_PATH = Path.home() / ".aicmd.yaml"

def _save_yaml(data: dict) -> None:
    # Simple yaml writer (no external lib needed)
    lines = []
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{k}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}: {vv}")
        else:
            lines.append(f"{k}: {v}")
    CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

@app.command()
def set(
    provider: str = typer.Option(..., "--provider", help="ollama or openrouter"),
    model: str = typer.Option(None, "--model", help="default model name"),
    ollama_url: str = typer.Option(None, "--ollama-url", help="URL of local Ollama server"),
    openrouter_key: str = typer.Option(None, "--openrouter-key", help="API key for OpenRouter"),
    timeout: int = typer.Option(None, "--timeout", help="Request timeout in seconds for summarize"),
):
    """Create or update ~/.aicmd.yaml with the supplied values."""
    cfg = cfg_mod.load()
    cfg.update({"provider": provider})
    if model is not None:
        cfg["model"] = model
    if ollama_url is not None:
        cfg["ollama_url"] = ollama_url
    if openrouter_key is not None:
        cfg["openrouter_key"] = openrouter_key
    _save_yaml(cfg)
    typer.echo(f"Configuration written to {CONFIG_PATH}")

@app.command(name="list-ollama-models")
def list_ollama_models(
    url: str = typer.Option(None, "--url", help="Ollama base URL (default from config)"),
    timeout: int = typer.Option(10, "--timeout", help="Request timeout in seconds"),
):
    """Print the names of all Ollama models currently installed locally."""
    base = url or cfg_mod.load().get("ollama_url", "http://localhost:11434")
    try:
        r = httpx.get(f"{base.rstrip('/')}/api/tags", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        models = [m.get("name") for m in data.get("models", [])]
        for m in models:
            typer.echo(m)
    except Exception as e:
        typer.echo(f"[error] Could not retrieve models: {e}", err=True)
        raise typer.Exit(code=1)
