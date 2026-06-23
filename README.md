# aicmd

AI‑powered Unix‑style command suite written in Python.

## Installation
```bash
pip install .   # from the repository root
```

## Usage
```bash
# Summarize text from a file
cat notes.txt | aicmd summarize

aicmd summarize --provider openrouter --model mistralai/mistral-7b-instruct report.md
```

The command reads from **STDIN** when no file is supplied, making it composable in pipelines.

## Configuration
Create `~/.aicmd.yaml` (or set env vars) to specify defaults:
```yaml
provider: ollama      # or openrouter
model: llama3:8b      # default model name
ollama_url: http://localhost:11434
openrouter_key: YOUR_API_KEY
```

## Extending
Add new sub‑commands under `aicmd/cli.py` and implement additional providers in `aicmd/providers/`.
