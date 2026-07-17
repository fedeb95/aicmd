import threading
import webview
import uvicorn

from aicmd.api import app


def start_api():
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )


threading.Thread(
    target=start_api,
    daemon=True
).start()


webview.create_window(
    "AICMD",
    "http://127.0.0.1:8000"
)

webview.start(gui="qt")
