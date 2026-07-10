#!/usr/bin/env python3
"""
serve_multilingual.py — Aziza Multilingual Text API
Novatech | AZIZA-BUILD-PLAN-PH2-PH3

Text-in / text-out endpoint for Aziza comprehending Russian, Uzbek Latin, and Uzbek Cyrillic.

Endpoints:
    GET  /health         → server + adapter status
    GET  /test/cyrillic  → automated 5-prompt smoke test
    POST /chat           → send text, get response

Usage:
    export HF_TOKEN=hf_your_token_here
    export MODEL_ID=Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24
    python3 serve_multilingual.py --language uz-cyrillic
    
Run via PM2:
    pm2 start "python3 serve_multilingual.py --language uz-cyrillic" --name aziza-backend-uz
"""

import json
import logging
import os
import sys
import time
import argparse
from contextlib import asynccontextmanager
from typing import Optional

sys.path.append(os.path.join(os.path.dirname(__file__), "backend", "persona-plex"))
from persona_plex_core import StreamingSafePersonaPlex

import torch
from threading import Lock

_generation_lock = Lock()


log = logging.getLogger("aziza.serve")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ── Config from environment ────────────────────────────────────────────────────

HF_TOKEN: str = os.environ.get("HF_TOKEN", "")
MODEL_ID: str = os.environ.get("MODEL_ID", "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24")
MAX_NEW_TOKENS: int = int(os.environ.get("MAX_NEW_TOKENS", "256"))
DEFAULT_TEMPERATURE: float = float(os.environ.get("DEFAULT_TEMPERATURE", "0.7"))
REQUEST_TIMEOUT_S: float = float(os.environ.get("REQUEST_TIMEOUT_S", "30.0"))

# Parse Language argument if run directly
LANGUAGE = os.environ.get("LANGUAGE", "ru")

parser = argparse.ArgumentParser(description="Aziza Backend API")
parser.add_argument("--language", type=str, default=LANGUAGE, help="Target language (ru, uz-cyrillic, uz-latin)")
parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8020")), help="Port to run on")
args, unknown = parser.parse_known_args()

LANGUAGE = args.language
PORT = args.port

ADAPTER_PATHS = {
    "ru": "/root/AZIZA-BUILD/backend/fine-tuning/aziza-adapter-final-ru/final",
    "uz-cyrillic": "/root/AZIZA-BUILD/backend/fine-tuning/aziza-adapter-final-uz/final",
    "uz-latin": "/root/AZIZA-BUILD/backend/fine-tuning/aziza-adapter-final-uz/final",
}

ADAPTER_PATH = os.environ.get("ADAPTER_PATH", ADAPTER_PATHS.get(LANGUAGE, ""))

# ── Globals (populated at startup) ────────────────────────────────────────────

_model = None
_tokenizer = None
_adapter_name: str = ""
_startup_error: Optional[str] = None
_startup_time: Optional[float] = None
persona_plex_client = StreamingSafePersonaPlex(redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"))

# ── Smoke test prompts (used by GET /test/cyrillic) ───────────────────────────

SMOKE_PROMPTS = [
    "Привет! Как тебя зовут?",
    "Расскажи мне о своих возможностях.",
    "Что такое искусственный интеллект?",
    "Помоги составить короткое деловое сообщение.",
    "Как дела? Ответь по-русски.",
]

SYSTEM_PROMPTS = {
    "ru": (
        "Ты — Aziza, дружелюбный и умный голосовой ИИ-ассистент. \n\n"
        "ПРАВИЛА ПОВЕДЕНИЯ:\n"
        "- Всегда отвечай на том языке, на котором говорит пользователь\n"
        "- Выполняй задачу ТОЧНО так, как просит пользователь\n"
        "- Если просят шутку — расскажи реальную смешную шутку\n"
        "- Если просят план — составь конкретный план\n"
        "- Если просят объяснение — объясни чётко и по делу\n"
        "- НИКОГДА не извиняйся в начале ответа без причины\n"
        "- НИКОГДА не говори \"я не могу\" если задача выполнима\n"
        "- Будь краткой и конкретной — не добавляй лишний текст\n\n"
        "ЗАПРЕЩЕНО:\n"
        "- Начинать ответ с \"Извините за ошибку\"\n"
        "- Отказываться от выполнимых задач\n"
        "- Добавлять нерелевантные советы\n"
        "- Повторять одно и то же разными словами"
    ),
    "uz-cyrillic": (
        "Сиз — Азиза, ақлли ва дўстона AI-ассистентсиз. "
        "Ҳар доим фақат ўзбек тилида (кирилл алифбосида) жавоб беринг."
    ),
    "uz-latin": (
        "Siz — Aziza, aqlli va do'stona AI-assistentsiz. "
        "Har doim faqat o'zbek tilida (lotin alifbosida) javob bering."
    ),
}

SYSTEM_PROMPT = SYSTEM_PROMPTS.get(LANGUAGE, SYSTEM_PROMPTS["ru"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def has_cyrillic(text: str) -> bool:
    return any(0x0400 <= ord(c) < 0x0500 for c in text)

def cyrillic_ratio(text: str) -> float:
    if not text:
        return 0.0
    cyrillic_chars = sum(1 for c in text if 0x0400 <= ord(c) < 0x0500)
    alpha_chars = sum(1 for c in text if c.isalpha())
    return round(cyrillic_chars / alpha_chars, 3) if alpha_chars > 0 else 0.0

def get_vram_info() -> dict:
    if not torch.cuda.is_available():
        return {"available": False}
    try:
        total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        used = torch.cuda.memory_allocated(0) / (1024 ** 3)
        return {
            "available": True,
            "device": torch.cuda.get_device_name(0),
            "total_gb": round(total, 1),
            "used_gb": round(used, 1),
            "free_gb": round(total - used, 1),
        }
    except Exception as e:
        return {"available": True, "error": str(e)}

# ── Model lifecycle ────────────────────────────────────────────────────────────

def _load_model() -> None:
    global _model, _tokenizer, _adapter_name, _startup_error, _startup_time

    t0 = time.perf_counter()

    if not HF_TOKEN:
        _startup_error = "HF_TOKEN environment variable not set"
        log.error(_startup_error)
        return

    adapter_path = ADAPTER_PATH
    use_adapter = bool(adapter_path)

    if use_adapter and not os.path.exists(adapter_path):
        _startup_error = f"ADAPTER_PATH does not exist: {adapter_path}"
        log.error(_startup_error)
        return

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as e:
        _startup_error = f"Missing transformers: {e}"
        log.error(_startup_error)
        return

    log.info(f"Loading tokenizer: {MODEL_ID}")
    _tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, token=HF_TOKEN, trust_remote_code=True
    )
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    log.info(f"Loading base model: {MODEL_ID}")
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        token=HF_TOKEN,
        trust_remote_code=True,
    )

    if use_adapter:
        try:
            from peft import PeftModel
            log.info(f"Loading QLoRA adapter: {adapter_path}")
            _model = PeftModel.from_pretrained(base_model, adapter_path, adapter_name=LANGUAGE)
            _adapter_name = LANGUAGE
            log.info(f"Adapter loaded: {_adapter_name}")
        except Exception as e:
            _startup_error = f"Failed to load adapter: {e}"
            log.error(_startup_error)
            return
    else:
        log.warning("No ADAPTER_PATH set — serving base model only (fallback mode)")
        _model = base_model
        _adapter_name = "base_model_only"

    _model.eval()
    _startup_time = round(time.perf_counter() - t0, 2)
    log.info(f"Model ready in {_startup_time}s. Adapter: {_adapter_name} ({LANGUAGE})")


def switch_adapter(target_lang: str):
    global LANGUAGE, _adapter_name, SYSTEM_PROMPT
    if target_lang not in ADAPTER_PATHS or target_lang == LANGUAGE:
        return
    
    path = ADAPTER_PATHS[target_lang]
    # Check fallback logic or specific path if environment variable is used
    if not os.path.exists(path):
        log.warning(f"Adapter path {path} not found. Trying to load anyway or skip.")
        return
        
    try:
        log.info(f"Switching adapter to {target_lang}...")
        _model.load_adapter(path, adapter_name=target_lang)
        _model.set_adapter(target_lang)
        LANGUAGE = target_lang
        _adapter_name = target_lang
        SYSTEM_PROMPT = SYSTEM_PROMPTS.get(target_lang, SYSTEM_PROMPTS["ru"])
        log.info(f"Successfully switched adapter to {target_lang}")
    except Exception as e:
        log.error(f"Failed to switch adapter to {target_lang}: {e}")



# ── Inference ──────────────────────────────────────────────────────────────────

def _generate(session_id: str, message: str, temperature: float, max_new_tokens: int) -> dict:
    raise RuntimeError("Call async_generate instead")

async def async_generate(session_id: str, message: str, temperature: float, max_new_tokens: int) -> dict:
    if not message or not message.strip():
        raise ValueError("message must not be empty")
    if len(message) > 4000:
        raise ValueError("message exceeds 4000 character limit")
    if temperature < 0.01 or temperature > 2.0:
        raise ValueError("temperature must be between 0.01 and 2.0")

    dynamic_prompt = await persona_plex_client.build_prompt(session_id, message)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": dynamic_prompt.strip()},
    ]
    try:
        input_text = _tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        input_text = f"<|user|>\n{message.strip()}\n<|assistant|>\n"

    inputs = _tokenizer(input_text, return_tensors="pt").to(_model.device)
    input_token_count = inputs["input_ids"].shape[1]

    t0 = time.perf_counter()
    with _generation_lock:
        with torch.no_grad():
            output_ids = _model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=0.9,
                top_k=50,
                repetition_penalty=1.15,
                pad_token_id=_tokenizer.eos_token_id,
            )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    new_tokens = output_ids[0][input_token_count:]
    output_token_count = len(new_tokens)
    response_text = _tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    return {
        "response": response_text,
        "has_cyrillic": has_cyrillic(response_text),
        "cyrillic_ratio": cyrillic_ratio(response_text),
        "input_tokens": input_token_count,
        "output_tokens": output_token_count,
        "total_ms": round(elapsed_ms, 1),
        "adapter": _adapter_name,
        "language": LANGUAGE,
    }


# ── FastAPI app ────────────────────────────────────────────────────────────────

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError as e:
    log.error(f"Missing FastAPI/pydantic: {e}. Install: pip install fastapi uvicorn pydantic")
    sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Aziza Multilingual server...")
    _load_model()
    await persona_plex_client.connect()
    if _startup_error:
        log.error(f"Startup failed: {_startup_error}")
    else:
        log.info("Server ready.")
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="Aziza Multilingual API",
    description="Text-in / text-out endpoint for Multilingual AI.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Ollama Compatibility ───────────────────────────────────────────────────────
from fastapi.responses import StreamingResponse
import asyncio
from threading import Thread
from transformers import TextIteratorStreamer

class OllamaChatRequest(BaseModel):
    model: str
    messages: list[dict]
    stream: bool = False
    options: dict = {}

@app.post("/api/chat")
async def ollama_chat(req: OllamaChatRequest):
    if _startup_error or _model is None:
        raise HTTPException(status_code=503, detail=f"Model not ready: {_startup_error}")

    session_id = req.options.get("session_id", "default")
    
    last_user_idx = -1
    for i in range(len(req.messages)-1, -1, -1):
        if req.messages[i]["role"] == "user":
            last_user_idx = i
            break
            
    if last_user_idx != -1:
        dynamic_prompt = await persona_plex_client.build_prompt(session_id, req.messages[last_user_idx]["content"])
        req.messages[last_user_idx]["content"] = dynamic_prompt
        
    if not any(m["role"] == "system" for m in req.messages):
        req.messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    else:
        for m in req.messages:
            if m["role"] == "system":
                m["content"] = f"{SYSTEM_PROMPT}\n{m['content']}"

    try:
        input_text = _tokenizer.apply_chat_template(
            req.messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        input_text = "\n".join([f"<|{m['role']}|>\n{m['content']}" for m in req.messages]) + "\n<|assistant|>\n"

    inputs = _tokenizer(input_text, return_tensors="pt").to(_model.device)
    
    streamer = TextIteratorStreamer(_tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    generation_kwargs = dict(
        **inputs,
        max_new_tokens=req.options.get("num_predict", MAX_NEW_TOKENS),
        do_sample=True,
        temperature=req.options.get("temperature", 0.7),
        top_p=0.9,
        top_k=50,
        repetition_penalty=1.15,
        pad_token_id=_tokenizer.eos_token_id,
        streamer=streamer,
    )
    
    # Check if we need to switch languages
    if req.model and req.model in ADAPTER_PATHS:
        with _generation_lock:
            switch_adapter(req.model)

    def locked_generate():
        with _generation_lock:
            _model.generate(**generation_kwargs)

    thread = Thread(target=locked_generate)
    thread.start()

    async def generate_stream():
        for text in streamer:
            chunk = {
                "model": req.model,
                "message": {"role": "assistant", "content": text},
                "done": False
            }
            yield json.dumps(chunk) + "\n"
            await asyncio.sleep(0.001)
            
        final_chunk = {
            "model": req.model,
            "message": {"role": "assistant", "content": ""},
            "done": True
        }
        yield json.dumps(final_chunk) + "\n"

    if req.stream:
        return StreamingResponse(generate_stream(), media_type="application/x-ndjson")
    else:
        thread.join()
        return JSONResponse(content={"error": "Non-streaming not supported"}, status_code=400)



# ── Request / response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000,
                         description="Input text")
    temperature: float = Field(default=0.7, ge=0.01, le=2.0)
    max_tokens: int = Field(default=256, ge=1, le=512)
    session_id: str = Field(default="default", description="Session ID for PersonaPlex context")

class ChatResponse(BaseModel):
    response: str
    has_cyrillic: bool
    cyrillic_ratio: float
    input_tokens: int
    output_tokens: int
    total_ms: float
    adapter: str
    language: str

class HealthResponse(BaseModel):
    status: str
    adapter: str
    language: str
    model_id: str
    startup_time_s: Optional[float]
    vram: dict
    error: Optional[str] = None


@app.get("/health", response_model=HealthResponse)
async def health():
    if _startup_error:
        return HealthResponse(
            status="error",
            adapter=ADAPTER_PATH,
            language=LANGUAGE,
            model_id=MODEL_ID,
            startup_time_s=None,
            vram=get_vram_info(),
            error=_startup_error,
        )
    return HealthResponse(
        status="ready",
        adapter=_adapter_name,
        language=LANGUAGE,
        model_id=MODEL_ID,
        startup_time_s=_startup_time,
        vram=get_vram_info(),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if _startup_error or _model is None:
        raise HTTPException(status_code=503, detail=f"Model not ready: {_startup_error}")

    log.info(f"/chat input ({len(req.message)} chars): {req.message[:80]}...")

    try:
        data = await async_generate(req.session_id, req.message, req.temperature, req.max_tokens)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except torch.cuda.OutOfMemoryError:
        raise HTTPException(
            status_code=503,
            detail="GPU out of memory — try a shorter message or restart the server",
        )
    except Exception as e:
        log.error(f"Inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Inference failed — check server logs")

    log.info(
        f"/chat response ({data['output_tokens']} tokens, "
        f"has_cyrillic={data['has_cyrillic']}, {data['total_ms']:.0f}ms)"
    )
    return ChatResponse(**data)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error — check server logs"},
    )

if __name__ == "__main__":
    import uvicorn
    log.info(f"Starting on port {PORT} with language {LANGUAGE}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, workers=1)
