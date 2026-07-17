import threading
import webview
import uvicorn

from aicmd.api import app

import subprocess
from aicmd.paths import app_path


def start_llama():

    server = app_path(
        "runtime",
        "linux",
        "llama-server"
    )

    model = app_path(
        "models",
        "qwen2.5-1.5b-instruct-q8_0.gguf"
    )

    process = subprocess.Popen(
        [
            server,
            "-m",
            model,
            "--host",
            "127.0.0.1",
            "--port",
            "8081"
        ]
    )

    return process

def start_api():
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )


llama_process = start_llama()

threading.Thread(
    target=start_api,
    daemon=True
).start()

webview.create_window(
    "AICMD",
    "http://127.0.0.1:8000"
)

llama_process = start_llama()

try:
    webview.start()

finally:
    llama_process.terminate()
