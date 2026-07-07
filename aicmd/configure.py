import yaml
import json
import os
from pathlib import Path
import typer
import httpx
from . import config as cfg_mod

app = typer.Typer(help="Helper commands for configuring providers")

CONFIG_PATH = Path.home() / ".aicmd.yaml"


def _load_file_only() -> dict:
    """Read ~/.aicmd.yaml directly, without env-var injection."""
    if not CONFIG_PATH.is_file():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded if isinstance(loaded, dict) else {}


def _save_yaml(data: dict) -> None:
    """Write *data* to ~/.aicmd.yaml using proper YAML serialisation."""
    CONFIG_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

@app.command()
def set(
    provider: str = typer.Option(None, "--provider", help="ollama or openrouter"),
    timeout: int = typer.Option(None, "--timeout", help="Request timeout in seconds for summarize"),
):
    """Create or update ~/.aicmd.yaml with the supplied values."""
    # Load only the file (no env vars) so we don't accidentally persist env values
    cfg = _load_file_only()
    if provider is not None:
        cfg["provider"] = provider
    if timeout is not None:
        cfg["timeout"] = timeout
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

@app.command(name="list-openrouter-models")
def list_openrouter_models(
    api_key: str = typer.Option(None, "--api-key", help="OpenRouter API key (overrides config)"),
    free_only: bool = typer.Option(False, "--free-only", help="Show only free-tier models"),
    timeout: int = typer.Option(15, "--timeout", help="Request timeout in seconds"),
):
    """List available OpenRouter models (optionally filter to free tier)."""
    key = api_key or cfg_mod.load().get("openrouter_key")
    if not key:
        typer.echo("[error] OpenRouter API key not configured", err=True)
        raise typer.Exit(code=1)
    try:
        headers = {"Authorization": f"Bearer {key}"}
        resp = httpx.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("data", [])
        for m in models:
            if free_only and not m.get("pricing", {}).get("price_per_1k_tokens"):
                continue
            typer.echo(f"{m.get('id')}: {m.get('name')}")
    except Exception as e:
        typer.echo(f"[error] Could not fetch OpenRouter models: {e}", err=True)
        raise typer.Exit(code=1)
