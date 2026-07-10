import os
import json
import logging
import asyncio
import redis.asyncio as redis
from datetime import datetime
from fastapi import FastAPI, HTTPException
from models import Persona, MemoryEntry, SessionContext, LoadPersonaRequest, SwitchPersonaRequest, MemoryStoreRequest, PromptBuildRequest
from database import db, get_persona, save_memory, get_session_history
from persona_plex_core import StreamingSafePersonaPlex

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PersonaPlex")

app = FastAPI(title="Aziza PersonaPlex")
from fastapi.responses import HTMLResponse
@app.get("/aziza-personaplex-test.html", response_class=HTMLResponse)
async def get_test_page():
    with open("/root/aziza-build/aziza-personaplex-test.html", "r") as f:
        return f.read()

redis_conn = None
plex_core = None

@app.on_event("startup")
async def startup():
    global redis_conn, plex_core
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = redis.from_url(redis_url)
    plex_core = StreamingSafePersonaPlex(redis_url=redis_url)
    await plex_core.connect()
    logger.info("PersonaPlex connected to Redis")
    
    # Start background task to monitor conversation tokens for memory
    asyncio.create_task(monitor_tokens())

async def monitor_tokens():
    """Listen to session:*:tokens and aggregate them into conversation history."""
    pubsub = redis_conn.pubsub()
    await pubsub.psubscribe("session:*:tokens")
    
    session_buffers = {} # session_id -> current_sentence
    
    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue
            
        channel = message["channel"].decode()
        session_id = channel.split(":")[1]
        token = message["data"].decode()
        
        if session_id not in session_buffers:
            session_buffers[session_id] = ""
            
        session_buffers[session_id] += token
        
        # Simple heuristic: end of sentence or enough tokens
        if any(punct in token for punct in [".", "?", "!"]) or len(session_buffers[session_id]) > 500:
            content = session_buffers[session_id].strip()
            if content:
                logger.info(f"Saving memory for {session_id}: {content}")
                await save_memory({
                    "session_id": session_id,
                    "content": content,
                    "sender": "ai",
                    "timestamp": datetime.utcnow()
                })
            session_buffers[session_id] = ""

@app.get("/sessions/{session_id}/context")
async def get_context(session_id: str):
    history = await get_session_history(session_id)
    return {"session_id": session_id, "history": history}

@app.post("/personas")
async def create_persona(persona: Persona):
    await db.personas.insert_one(persona.dict(by_alias=True))
    return {"status": "ok"}

@app.post("/sessions/load")
async def load_persona(req: LoadPersonaRequest):
    await plex_core.load_persona(req.session_id, req.persona_id, req.language, req.emotion_state)
    return {"status": "loaded", "session_id": req.session_id}

@app.post("/sessions/switch")
async def switch_persona(req: SwitchPersonaRequest):
    await plex_core.switch_persona(req.session_id, req.persona_id, req.language, req.emotion_state)
    return {"status": "switched", "session_id": req.session_id}

@app.post("/sessions/memory")
async def store_memory(req: MemoryStoreRequest):
    await save_memory({
        "session_id": req.session_id,
        "content": req.content,
        "sender": req.sender,
        "timestamp": datetime.utcnow()
    })
    return {"status": "memory_stored"}

@app.post("/sessions/prompt")
async def build_prompt(req: PromptBuildRequest):
    prompt = await plex_core.build_prompt(req.session_id, req.user_message)
    return {"prompt": prompt}

from pydantic import BaseModel
class LangDetectRequest(BaseModel):
    text: str

@app.post("/lang/detect")
async def detect_lang(req: LangDetectRequest):
    import re
    if re.search(r'[а-яА-ЯёЁ]', req.text):
        return {"language": "ru"}
    return {"language": "en"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
