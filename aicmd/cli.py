import sys
import typer
from . import configure
from pathlib import Path
from . import config, providers, services

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
    # read input
    if file is None:
        text = sys.stdin.read()
    else:
        text = file.read_text()

    has_streamed = False
    def stream_callback(chunk: str):
        nonlocal has_streamed
        has_streamed = True
        sys.stdout.write(chunk)
        sys.stdout.flush()

    try:
        summary = services.summarize_text(
            text,
            provider=provider or None,
            model=model or None,
            max_tokens=max_tokens,
            timeout=timeout,
            stream_callback=stream_callback,
        )
        if not has_streamed:
            typer.echo(summary)
        else:
            typer.echo("") # trailing newline
    except Exception as e:
        typer.echo(f"[error] {str(e)}", err=True)
        raise typer.Exit(code=1)

@app.command()
def describe(
    image: Path = typer.Argument(..., help="Path to the image file to describe"),
    provider: str = typer.Option("", help="ollama|openrouter; auto‑detect if omitted"),
    model: str = typer.Option("", help="Model name; provider default if omitted"),
    max_tokens: int = typer.Option(256, help="Maximum tokens for the description"),
    timeout: int = typer.Option(None, help="Request timeout in seconds (overrides config)"),
):
    """Describe an input image using the selected LLM backend (default Moondream)."""
    try:
        description = services.describe_image(
            image,
            provider=provider or None,
            model=model or None,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        typer.echo(description)
    except Exception as e:
        typer.echo(f"[error] {str(e)}", err=True)
        raise typer.Exit(code=1)

@app.command()
def rewrite(
    style: str = typer.Argument(..., help="The style description or instructions to rewrite the text"),
    file: Path = typer.Argument(None, help="File to read; reads stdin if omitted"),
    provider: str = typer.Option("", help="ollama|openrouter; auto‑detect if omitted"),
    model: str = typer.Option("", help="Model name; provider default if omitted"),
    max_tokens: int = typer.Option(256, help="Maximum tokens for the rewritten text"),
    timeout: int = typer.Option(None, help="Request timeout in seconds (overrides config)"),
):
    """Rewrite input text using a specified style/instruction."""
    # read input
    if file is None:
        text = sys.stdin.read()
    else:
        text = file.read_text()

    has_streamed = False
    def stream_callback(chunk: str):
        nonlocal has_streamed
        has_streamed = True
        sys.stdout.write(chunk)
        sys.stdout.flush()

    try:
        rewritten = services.rewrite_text(
            text,
            style,
            provider=provider or None,
            model=model or None,
            max_tokens=max_tokens,
            timeout=timeout,
            stream_callback=stream_callback,
        )
        if not has_streamed:
            typer.echo(rewritten)
        else:
            typer.echo("") # trailing newline
    except Exception as e:
        typer.echo(f"[error] {str(e)}", err=True)
        raise typer.Exit(code=1)

@app.command()
def chat(
    chat_id: str = typer.Option("", help="Existing chat id to continue"),
    message: str = typer.Argument(None, help="Message to send; if omitted reads stdin and sends it as the message"),
    provider: str = typer.Option("", help="ollama|openrouter; auto‑detect if omitted"),
    model: str = typer.Option("", help="Model name; provider default if omitted"),
    max_tokens: int = typer.Option(256, help="Maximum tokens for the response"),
    timeout: int = typer.Option(None, help="Request timeout in seconds (overrides config)"),
):
    """Send a single message in an in-memory chat and print `chatid:message` on a single line.

    Reads stdin if piped. Does NOT start a REPL. Always performs a one-off turn and exits.
    """
    # read stdin if piped
    stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        if message is None and stdin_text.strip():
            message = stdin_text
        if message is None:
            typer.echo("[error] No message provided (pass as argument or via stdin)", err=True)
            raise typer.Exit(code=2)

        # Ensure chat exists and get id so it can be printed before streaming
        cid = services.create_chat(chat_id or None)

        has_streamed = False
        def stream_print(chunk: str):
            nonlocal has_streamed
            has_streamed = True
            # write chunk directly after the id prefix
            sys.stdout.write(chunk)
            sys.stdout.flush()

        # print id prefix without newline, stream will follow
        sys.stdout.write(f"{cid}:")
        sys.stdout.flush()

        cid_returned, reply = services.send_chat_message(
            cid,
            message,
            provider=provider or None,
            model=model or None,
            max_tokens=max_tokens,
            timeout=timeout,
            stream_callback=stream_print,
        )

        # If provider didn't stream, print the reply now
        if not has_streamed:
            sys.stdout.write(reply or "")
            sys.stdout.flush()
        # finish with newline
        sys.stdout.write("\n")
        typer.echo("", nl=False)
    except Exception as e:
        typer.echo(f"[error] {str(e)}", err=True)
        raise typer.Exit(code=1)


@app.command()
def translate(
    target: str = typer.Option(..., "--to", "-t", help="Target language (e.g., en, es, fr or 'English', 'Spanish')"),
    source: str = typer.Option("", "--from", "-f", help="Source language (optional)"),
    file: Path = typer.Argument(None, help="File to read; reads stdin if omitted"),
    provider: str = typer.Option("", help="ollama|openrouter; auto‑detect if omitted"),
    model: str = typer.Option("", help="Model name; provider default if omitted"),
    max_tokens: int = typer.Option(512, help="Maximum tokens for the translation"),
    timeout: int = typer.Option(None, help="Request timeout in seconds (overrides config)"),
):
    """Translate input text to the specified target language.

    Reads stdin when no file is provided. Outputs the translated text to stdout. Supports streaming when provider supports it.
    """
    # read input
    if file is None:
        text = sys.stdin.read()
    else:
        text = file.read_text()

    has_streamed = False
    def stream_callback(chunk: str):
        nonlocal has_streamed
        has_streamed = True
        sys.stdout.write(chunk)
        sys.stdout.flush()

    try:
        translated = services.translate_text(
            text,
            target,
            source or None,
            provider=provider or None,
            model=model or None,
            max_tokens=max_tokens,
            timeout=timeout,
            stream_callback=stream_callback,
        )
        if not has_streamed:
            typer.echo(translated)
        else:
            typer.echo("")
    except Exception as e:
        typer.echo(f"[error] {str(e)}", err=True)
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address"),
    port: int = typer.Option(8000, help="Port to listen on"),
):
    """Start the API server exposing aicmd functionalities."""
    import uvicorn
    typer.echo(f"Starting API server on http://{host}:{port}...")
    uvicorn.run("aicmd.api:app", host=host, port=port, reload=True)

app.add_typer(configure.app, name="configure")

if __name__ == "__main__":
    app()
