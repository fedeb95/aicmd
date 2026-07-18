import threading
import webview
import uvicorn

from aicmd.api import app

import subprocess
from aicmd.paths import app_path

llama_process = None

def start_llama():

    global llama_process

    server = app_path(
        "runtime",
        "linux",
        "llama-server"
    )

    model = app_path(
        "models",
        "SmolVLM-500M-Instruct-f16.gguf"
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
            "--mmproj",
            multimodal, 
            "--host",
            "127.0.0.1",
            "--port",
            "8081"
        ]
    )

    return llama_process

def start_api():
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )

def on_closing():
    global llama_process

    if llama_process:
        llama_process.terminate()

        try:
            llama_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            llama_process.kill()


llama_process = start_llama()

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
    llama_process.terminate()
