# aicmd

AI‑powered Unix‑style command suite written in Python.

## Installation
```bash
pip install .   # from the repository root
```

## Usage
```bash
# Configure a provider (example for Ollama)
# You can also set a timeout that applies to all summarize calls

aicmd configure set \
    --provider ollama \
    --model llama3:8b \
    --ollama-url http://localhost:11434 \
    --timeout 300

# Summarize text from STDIN or a file
cat notes.txt | aicmd summarize

aicmd summarize notes.txt
```

The command reads from **STDIN** when no file is supplied, making it composable in pipelines.

## Provider utilities
```bash
# List installed Ollama models
aicmd configure list-ollama-models

# List available OpenRouter models (show only free tier)
aicmd configure list-openrouter-models --free-only
```

## Configuration file
Your `~/.aicmd.yaml` will contain entries you set, e.g.:
```yaml
provider: ollama
model: qwen2.5:0.5b
ollama_url: http://localhost:11434
# timeout is optional and defaults to 300 seconds if not set
# openrouter_key: <your‑key>   # only needed for OpenRouter
```
The configuration above has been tested with an Intel Celeron J4125 and 8GB of RAM, with Linux Kernel: 6.18.12-1-MANJARO x86_64.

## Extending
Add new sub‑commands under `aicmd/cli.py` and implement additional providers in `aicmd/providers/`.
