import os
import shutil
import tempfile
import json
import queue
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


import asyncio
import queue
import threading
from fastapi.responses import StreamingResponse

# Helper to run synchronous service functions in a background thread
# and yield their chunks in real-time to StreamingResponse.
def run_in_thread_with_stream(func, *args, **kwargs):
    """
    Runs a synchronous function in a background thread, collecting its
    streamed output via a thread-safe queue.Queue, and yields chunks
    via an async generator using non-blocking polling.
    """
    q = queue.Queue()

    def cb(chunk: str):
        # Thread-safe put into the synchronous queue
        q.put(chunk)

    def worker():
        try:
            func(*args, stream_callback=cb, **kwargs)
        except Exception as e:
            q.put(e)
        finally:
            q.put(None)  # Sentinel to signal completion

    thread = threading.Thread(target=worker)
    thread.start()

    async def generator():
        while True:
            try:
                # Non-blocking check: if queue is empty, yield control briefly
                if q.empty():
                    await asyncio.sleep(0.01)
                    continue
                item = q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue

            if item is None:
                break
            if isinstance(item, Exception):
                yield f"data: {json.dumps({'error': str(item)})}\n\n"
                break
            yield f"data: {json.dumps({'chunk': item})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


class SummarizeRequest(BaseModel):
    text: str
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = 256
    timeout: Optional[int] = None
    stream: Optional[bool] = False

@app.post("/api/summarize")
async def summarize(request: SummarizeRequest):
    try:
        if request.stream:
            return run_in_thread_with_stream(
                services.summarize_text,
                text=request.text,
                provider=request.provider,
                model=request.model,
                max_tokens=request.max_tokens or 256,
                timeout=request.timeout,
            )
        else:
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
    stream: Optional[bool] = False

@app.post("/api/rewrite")
async def rewrite(request: RewriteRequest):
    try:
        if request.stream:
            return run_in_thread_with_stream(
                services.rewrite_text,
                text=request.text,
                style=request.style,
                provider=request.provider,
                model=request.model,
                max_tokens=request.max_tokens or 256,
                timeout=request.timeout,
            )
        else:
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
    stream: Optional[bool] = False

@app.post("/api/translate")
async def translate(request: TranslateRequest):
    try:
        if request.stream:
            return run_in_thread_with_stream(
                services.translate_text,
                text=request.text,
                target_lang=request.target,
                source_lang=request.source,
                provider=request.provider,
                model=request.model,
                max_tokens=request.max_tokens or 256,
                timeout=request.timeout,
            )
        else:
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

@app.post("/api/chat/new")
def create_new_chat():
    try:
        chat_id = services.create_chat()
        return {"chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/{chat_id}/history")
def get_chat_history(chat_id: str):
    try:
        messages = services.get_chat_history(chat_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    chat_id: str
    message: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = 512
    timeout: Optional[int] = None
    stream: Optional[bool] = False
    
    # Parametri per l'Agente AI
    use_agent: Optional[bool] = False
    tool_approved: Optional[bool] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None

@app.post("/api/chat")
async def send_chat_message(request: ChatRequest):
    try:
        if request.use_agent:
            # Se stiamo gestendo la risposta a una richiesta di approvazione di un tool
            if request.tool_approved is not None:
                def run_agent_post_approval(chat_id, tool_approved, tool_name, tool_args, provider, model, stream_callback):
                    # 1. Esegui il tool o registra il rifiuto
                    if tool_approved:
                        observation = services.execute_agent_tool(tool_name, tool_args)
                        if stream_callback:
                            stream_callback(json.dumps({
                                "approval_result": "approved",
                                "tool_name": tool_name,
                                "observation": observation
                            }))
                    else:
                        observation = "L'azione è stata negata dall'utente."
                        if stream_callback:
                            stream_callback(json.dumps({
                                "approval_result": "denied",
                                "tool_name": tool_name
                            }))

                    # 2. Salva nel database l'osservazione
                    action_desc = f"Action: {tool_name}({json.dumps(tool_args)})"
                    services.append_message(chat_id, "thought", action_desc)
                    services.append_message(chat_id, "observation", f"Observation: {observation}")

                    # 3. Fai continuare il ciclo ReAct (emette i suoi eventi "step")
                    return services.run_agent_loop(
                        chat_id=chat_id,
                        message=None,
                        provider=provider,
                        model=model,
                        stream_callback=stream_callback
                    )
                
                if request.stream:
                    return run_in_thread_with_stream(
                        run_agent_post_approval,
                        chat_id=request.chat_id,
                        tool_approved=request.tool_approved,
                        tool_name=request.tool_name,
                        tool_args=request.tool_args,
                        provider=request.provider,
                        model=request.model
                    )
                else:
                    # Chiamata sincrona (non in streaming)
                    # Non usiamo stream_callback
                    if request.tool_approved:
                        observation = services.execute_agent_tool(request.tool_name, request.tool_args)
                    else:
                        observation = "L'azione è stata negata dall'utente."
                    action_desc = f"Action: {request.tool_name}({json.dumps(request.tool_args)})"
                    services.append_message(request.chat_id, "thought", action_desc)
                    services.append_message(request.chat_id, "observation", f"Observation: {observation}")
                    
                    reply = services.run_agent_loop(
                        chat_id=request.chat_id,
                        message=None,
                        provider=request.provider,
                        model=request.model
                    )
                    return {"chat_id": request.chat_id, "reply": reply}
            
            # Altrimenti è un messaggio standard inviato all'Agente
            else:
                if request.stream:
                    return run_in_thread_with_stream(
                        services.run_agent_loop,
                        chat_id=request.chat_id,
                        message=request.message,
                        provider=request.provider,
                        model=request.model
                    )
                else:
                    reply = services.run_agent_loop(
                        chat_id=request.chat_id,
                        message=request.message,
                        provider=request.provider,
                        model=request.model
                    )
                    return {"chat_id": request.chat_id, "reply": reply}
        
        # Flusso di chat pura esistente (senza agente)
        else:
            if request.stream:
                return run_in_thread_with_stream(
                    services.send_chat_message,
                    chat_id=request.chat_id,
                    message=request.message,
                    provider=request.provider,
                    model=request.model,
                    max_tokens=request.max_tokens or 512,
                    timeout=request.timeout,
                )
            else:
                chat_id, reply = services.send_chat_message(
                    chat_id=request.chat_id,
                    message=request.message,
                    provider=request.provider,
                    model=request.model,
                    max_tokens=request.max_tokens or 512,
                    timeout=request.timeout,
                )
                return {"chat_id": chat_id, "reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
