#!/usr/bin/env python3
"""
serve_russian_test.py — Aziza Russian text test API (Proxy Version)
Novatech | AZIZA-BUILD-PLAN-PH2-PH3

Proxies requests to the vLLM English service which hosts the Russian adapter.
"""
import os
import sys
import time
import httpx
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

log = logging.getLogger("aziza.serve")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8002/v1/chat/completions")
MODEL_ID = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
ADAPTER_NAME = "aziza_russian"

SMOKE_PROMPTS = [
    "Привет! Как тебя зовут?",
    "Расскажи мне о своих возможностях.",
    "Что такое искусственный интеллект?",
    "Помоги составить короткое деловое сообщение.",
    "Как дела? Ответь по-русски.",
]

def has_cyrillic(text: str) -> bool:
    return any(0x0400 <= ord(c) < 0x0500 for c in text)

def cyrillic_ratio(text: str) -> float:
    if not text: return 0.0
    cyrillic_chars = sum(1 for c in text if 0x0400 <= ord(c) < 0x0500)
    alpha_chars = sum(1 for c in text if c.isalpha())
    return round(cyrillic_chars / alpha_chars, 3) if alpha_chars > 0 else 0.0

app = FastAPI(title="Aziza Russian Text Test API", description="Proxy to vLLM.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    temperature: float = Field(default=0.7, ge=0.01, le=2.0)
    max_tokens: int = Field(default=256, ge=1, le=512)

class ChatResponse(BaseModel):
    response: str
    has_cyrillic: bool
    cyrillic_ratio: float
    input_tokens: int
    output_tokens: int
    total_ms: float
    adapter: str

class HealthResponse(BaseModel):
    status: str
    adapter: str
    model_id: str
    startup_time_s: Optional[float]
    vram: dict
    error: Optional[str] = None

class SmokeTestResult(BaseModel):
    prompt: str
    response: str
    has_cyrillic: bool
    cyrillic_ratio: float
    total_ms: float
    passed: bool

class SmokeTestResponse(BaseModel):
    all_pass: bool
    ready_for_demo: bool
    pass_count: int
    total: int
    results: list[SmokeTestResult]

async def _generate(message: str, temperature: float, max_tokens: int) -> dict:
    t0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        payload = {
            "model": ADAPTER_NAME,
            "messages": [{"role": "user", "content": message}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        resp = await client.post(VLLM_URL, json=payload, timeout=30.0)
        if resp.status_code != 200:
            # Try falling back to the base model name if adapter name is not recognized
            payload["model"] = MODEL_ID
            resp = await client.post(VLLM_URL, json=payload, timeout=30.0)
            if resp.status_code != 200:
                raise Exception(f"vLLM error: {resp.text}")
                
        data = resp.json()
        response_text = data["choices"][0]["message"]["content"].strip()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        
        return {
            "response": response_text,
            "has_cyrillic": has_cyrillic(response_text),
            "cyrillic_ratio": cyrillic_ratio(response_text),
            "input_tokens": data["usage"]["prompt_tokens"],
            "output_tokens": data["usage"]["completion_tokens"],
            "total_ms": round(elapsed_ms, 1),
            "adapter": data["model"]
        }

@app.get("/health", response_model=HealthResponse)
async def health():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(VLLM_URL.replace("/chat/completions", "/models"), timeout=5.0)
            if resp.status_code == 200:
                return HealthResponse(
                    status="ready", adapter=ADAPTER_NAME, model_id=MODEL_ID,
                    startup_time_s=0.0, vram={"available": True, "proxy": True}
                )
    except Exception as e:
        return HealthResponse(
            status="error", adapter=ADAPTER_NAME, model_id=MODEL_ID,
            startup_time_s=0.0, vram={"available": False, "proxy": True}, error=str(e)
        )
    return HealthResponse(
        status="error", adapter=ADAPTER_NAME, model_id=MODEL_ID,
        startup_time_s=0.0, vram={"available": False, "proxy": True}, error="Unknown"
    )

@app.get("/test/cyrillic", response_model=SmokeTestResponse)
async def test_cyrillic():
    results = []
    for prompt in SMOKE_PROMPTS:
        try:
            data = await _generate(prompt, 0.7, 128)
            results.append(SmokeTestResult(
                prompt=prompt, response=data["response"], has_cyrillic=data["has_cyrillic"],
                cyrillic_ratio=data["cyrillic_ratio"], total_ms=data["total_ms"], passed=data["has_cyrillic"]
            ))
        except Exception as e:
            results.append(SmokeTestResult(
                prompt=prompt, response=f"ERROR: {e}", has_cyrillic=False,
                cyrillic_ratio=0.0, total_ms=0.0, passed=False
            ))
    pass_count = sum(1 for r in results if r.passed)
    all_pass = pass_count == len(SMOKE_PROMPTS)
    return SmokeTestResponse(
        all_pass=all_pass, ready_for_demo=all_pass, pass_count=pass_count,
        total=len(SMOKE_PROMPTS), results=results
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        data = await _generate(req.message, req.temperature, req.max_tokens)
        return ChatResponse(**data)
    except Exception as e:
        log.error(f"Inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8020))
    uvicorn.run("serve_russian_test:app", host="0.0.0.0", port=port, workers=1)

# ─────────────────────────────────────────────────────────────────────────────
# POST /transcribe  — Speech-to-Text using faster-whisper (tiny multilingual)
# ─────────────────────────────────────────────────────────────────────────────
import tempfile
import subprocess
from pathlib import Path
from pydantic import BaseModel as _BaseModel
from fastapi import UploadFile, File as _File, Form as _Form

class TranscribeResponse(_BaseModel):
    transcription: str
    detected_language: str
    language_probability: float
    duration_s: float

_whisper_model = None

def _get_whisper():
    """Lazy-load the tiny multilingual faster-whisper model (CPU, int8)."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        log.info("Loading faster-whisper tiny model...")
        _whisper_model = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8",
            download_root="/root/aziza-build/model_cache/whisper"
        )
        log.info("faster-whisper ready.")
    return _whisper_model


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = _File(...),
    language: str = _Form(default=""),
):
    """
    Accept a WebM/OGG/WAV audio upload, convert to 16kHz WAV with ffmpeg,
    then transcribe with faster-whisper tiny model.
    Returns transcription text, detected language, confidence, and duration.
    """
    t0 = time.perf_counter()
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(await audio.read())
        tmp_in_path = tmp_in.name

    tmp_wav_path = tmp_in_path + ".wav"

    try:
        # Convert to 16kHz mono WAV (required by whisper)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path,
             "-ar", "16000", "-ac", "1", "-f", "wav", tmp_wav_path],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"ffmpeg conversion failed: {result.stderr.decode()[:300]}"
            )

        model = _get_whisper()
        # If language hint provided use it, else auto-detect
        lang_hint = language if language in ("ru", "uz", "en") else None
        segments, info = model.transcribe(
            tmp_wav_path,
            language=lang_hint,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.perf_counter() - t0

        return TranscribeResponse(
            transcription=text or "(inaudible)",
            detected_language=info.language,
            language_probability=round(info.language_probability, 3),
            duration_s=round(elapsed, 3),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"/transcribe error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)
        Path(tmp_wav_path).unlink(missing_ok=True)
