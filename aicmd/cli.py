import sys
import typer
from . import configure
from pathlib import Path
from . import config, providers

app = typer.Typer(help="AI‑powered Unix‑style commands")

@app.command()
def summarize(
    file: Path = typer.Argument(None, help="File to read; reads stdin if omitted"),
    provider: str = typer.Option("", help="ollama|openrouter; auto‑detect if omitted"),
    model: str = typer.Option("", help="Model name; provider default if omitted"),
    max_tokens: int = typer.Option(256, help="Maximum tokens for the summary"),
    timeout: int = typer.Option(None, help="Request timeout in seconds (overrides config)")
):
    """Summarize input text using the selected LLM backend."""
    cfg = config.load()
    prov = providers.get_provider(provider or cfg.get("provider"))
    if not prov:
        typer.echo("[error] No provider configured or supplied", err=True)
        raise typer.Exit(code=1)

    # read input
    if file is None:
        text = sys.stdin.read()
    else:
        text = file.read_text()

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    summary = prov.summarize(
        text,
        model=model or cfg.get("model"),
        max_tokens=max_tokens,
        timeout=effective_timeout,
    )
    typer.echo(summary)

app.add_typer(configure.app, name="configure")

if __name__ == "__main__":
    app()
