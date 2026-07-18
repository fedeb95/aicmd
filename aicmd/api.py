import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import services

import os
import sys

# Queste vengono iniettate da main.py quando si gira come app desktop
start_llama_fn = None
stop_llama_fn = None
get_llama_process_fn = None

def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        # PyInstaller
        base_path = sys._MEIPASS
    else:
        # sviluppo normale
        base_path = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

    return os.path.join(base_path, relative_path)


frontend_path = resource_path("frontend")

app = FastAPI(
    title="aicmd API",
    description="API interface for the aicmd functionalities (text summarization and image description)",
    version="0.1.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to match your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SummarizeRequest(BaseModel):
    text: str
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = 256
    timeout: Optional[int] = None

@app.post("/api/summarize")
def summarize(request: SummarizeRequest):
    try:
        summary = services.summarize_text(
            text=request.text,
            provider=request.provider,
            model=request.model,
            max_tokens=request.max_tokens or 256,
            timeout=request.timeout,
        )
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RewriteRequest(BaseModel):
    text: str
    style: str
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = 256
    timeout: Optional[int] = None

@app.post("/api/rewrite")
def rewrite(request: RewriteRequest):
    try:
        rewritten = services.rewrite_text(
            text=request.text,
            style=request.style,
            provider=request.provider,
            model=request.model,
            max_tokens=request.max_tokens or 256,
            timeout=request.timeout,
        )
        return {"rewritten": rewritten}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TranslateRequest(BaseModel):
    text: str
    target: str
    source: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = 256
    timeout: Optional[int] = None

@app.post("/api/translate")
def translate(request: TranslateRequest):
    try:
        translated = services.translate_text(
            text=request.text,
            target_lang=request.target,
            source_lang=request.source,
            provider=request.provider,
            model=request.model,
            max_tokens=request.max_tokens or 256,
            timeout=request.timeout,
        )
        return {"translated": translated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/describe")
async def describe(
    file: UploadFile = File(...),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    max_tokens: Optional[int] = Form(256),
    timeout: Optional[int] = Form(None),
):
    # Save the uploaded file to a temporary location
    temp_dir = tempfile.mkdtemp()
    temp_file_path = Path(temp_dir) / file.filename
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        description = services.describe_image(
            image_path=temp_file_path,
            provider=provider,
            model=model,
            max_tokens=max_tokens or 256,
            timeout=timeout,
        )
        return {"description": description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the temporary file and directory
        if temp_file_path.exists():
            temp_file_path.unlink()
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

@app.get("/api/models")
def list_models(provider: Optional[str] = None):
    """Return available models for the given provider (ollama or openrouter).
    Falls back to the configured default provider if none is specified.
    """
    import httpx as _httpx
    from . import config as _cfg

    cfg = _cfg.load()
    prov = (provider or cfg.get("provider") or "ollama").lower()

    try:
        if prov == "ollama":
            base = cfg.get("ollama_url", "http://localhost:11434").rstrip("/")
            r = _httpx.get(f"{base}/api/tags", timeout=8)
            r.raise_for_status()
            models = [m.get("name") for m in r.json().get("models", [])]
            return {"provider": prov, "models": models}

        elif prov == "openrouter":
            key = cfg.get("openrouter_key")
            if not key:
                raise HTTPException(status_code=400, detail="OpenRouter API key not configured")
            headers = {"Authorization": f"Bearer {key}"}
            r = _httpx.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=12)
            r.raise_for_status()
            models = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
            models.sort()
            return {"provider": prov, "models": models}

        elif prov == "llamaserver":
            # llama-server espone un endpoint OpenAI-compatibile
            base = cfg.get("llamaserver_url", "http://127.0.0.1:8081").rstrip("/")
            try:
                r = _httpx.get(f"{base}/v1/models", timeout=5)
                r.raise_for_status()
                models = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
            except Exception:
                # llama-server potrebbe non esporre /v1/models, restituiamo lista vuota
                models = []
            return {"provider": prov, "models": models}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {prov}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch models: {e}")


# ---- Gestione ciclo di vita llama-server ----

@app.post("/api/llama/start")
def llama_start():
    """Avvia il processo llama-server bundled."""
    if start_llama_fn is None:
        raise HTTPException(status_code=501, detail="Controllo llama-server non disponibile in modalità standalone")
    try:
        proc = start_llama_fn()
        if proc is None:
            raise HTTPException(status_code=500, detail="Impossibile avviare llama-server (binario non trovato?)")
        return {"status": "started", "pid": proc.pid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llama/stop")
def llama_stop():
    """Ferma il processo llama-server bundled."""
    if stop_llama_fn is None:
        raise HTTPException(status_code=501, detail="Controllo llama-server non disponibile in modalità standalone")
    try:
        stop_llama_fn()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/llama/status")
def llama_status():
    """Restituisce lo stato corrente del processo llama-server."""
    if get_llama_process_fn is None:
        return {"running": False, "pid": None, "managed": False}
    proc = get_llama_process_fn()
    running = proc is not None and proc.poll() is None
    return {
        "running": running,
        "pid": proc.pid if running else None,
        "managed": True,
    }


# Statici
app.mount(
    "/",
    StaticFiles(directory=frontend_path, html=True),
    name="frontend"
)

# Home page
@app.get("/")
def index():
    return FileResponse("frontend/index.html")
