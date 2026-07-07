import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import services

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

        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {prov}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch models: {e}")
