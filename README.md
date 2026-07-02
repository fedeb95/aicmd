# aicmd

AI‑powered Unix‑style command suite written in Python.

## Installation
```bash
pip install .   # from the repository root
```

## Setup 
```bash
# Configure a provider (example for Ollama)
# You can also set a timeout that applies to all summarize calls

aicmd configure set \
    --provider ollama \
    --model qwen2.5:0.5b-instruct \
    --ollama-url http://localhost:11434 \
    --timeout 300
```

## Usage

### Summarize text from STDIN or a file
cat notes.txt | aicmd summarize

```
aicmd summarize notes.txt
```

The command reads from **STDIN** when no file is supplied, making it composable in pipelines.

### Describe an image

```
aicmd describe image.png # or jpg
```

The command reads the image and outputs a short description with a vision model.


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
timeout: 3000
provider: ollama
ollama_summarize_model: deepseek-coder:1.3b
ollama_describe_model: ahmadwaqar/smolvlm2-256m-video:q8_0
ollama_url: http://localhost:11434
# openrouter_key: <your‑key>   # only needed for OpenRouter
```

The configuration above has been tested with no GPU, an Intel Celeron J4125 and 8GB of RAM, with Linux Kernel: 6.18.12-1-MANJARO x86_64.

Both summarize and describe work very well with ~1 page long text and ~1MB size images.

Better hardware makes it possibile to use better model and obtain faster and/or better answers.

## Extending
Add new sub‑commands under `aicmd/cli.py` and implement additional providers in `aicmd/providers/`.

Contributions are welcome!
