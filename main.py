import threading
import webview
import uvicorn

from aicmd.api import app

import subprocess
from aicmd.paths import app_path

llama_process = None

def start_llama():
    global llama_process

    # Se c'è già un processo in esecuzione, non avviarne un altro
    if llama_process and llama_process.poll() is None:
        return llama_process

    server = app_path(
        "runtime",
        "linux",
        "llama-server"
    )

    model = app_path(
        "models",
        "qwen2.5-1.5b-instruct-q8_0.gguf"
    )

    multimodal = app_path(
        "models",
        "mmproj-SmolVLM-500M-Instruct-f16.gguf"
    )

    llama_process = subprocess.Popen(
        [
            server,
            "-m",
            model,
            #"--mmproj",
            #multimodal,
            "-t",
            "4",
            "--threads-batch",
            "8",
            "-b",
            "1024",
            "-ub",
            "1024",
            "-c",
            "2048",
            "--host",
            "127.0.0.1",
            "--port",
            "8081"
        ]
    )

    return llama_process

def stop_llama():
    global llama_process

    if llama_process and llama_process.poll() is None:
        llama_process.terminate()
        try:
            llama_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            llama_process.kill()
        llama_process = None

def get_llama_process():
    return llama_process

# Esponi le funzioni di controllo all'API
import aicmd.api as _api_module
_api_module.start_llama_fn = start_llama
_api_module.stop_llama_fn = stop_llama
_api_module.get_llama_process_fn = get_llama_process

def start_api():
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )

def on_closing():
    stop_llama()

# ── Avvio automatico llama-server ──────────────────────────────────────────
# Se il provider configurato (o il default) è llamaserver, avviamo subito
# il processo bundled in background prima di aprire la finestra.
from aicmd import config as _cfg
_cfg_data = _cfg.load()
_provider = _cfg_data.get("provider", "").lower()

if _provider == "llamaserver":
    threading.Thread(target=start_llama, daemon=True).start()

# ───────────────────────────────────────────────────────────────────────────

threading.Thread(
    target=start_api,
    daemon=True
).start()

window = webview.create_window(
    "AICMD",
    "http://127.0.0.1:8000"
)

window.events.closing += on_closing

try:
    webview.start()

finally:
    stop_llama()
