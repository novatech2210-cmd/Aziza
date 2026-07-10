from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import redis.asyncio as aioredis
from app.core.redis_client import get_redis
from app.models.session import PersonaSession
import json

router = APIRouter()

class LoadPersonaRequest(BaseModel):
    session_id: str
    user_id: str
    persona_id: str
    language: str
    emotion_state: str = "neutral"

class SwitchPersonaRequest(BaseModel):
    session_id: str
    persona_id: str
    language: str

@router.post("/load")
async def load_persona(req: LoadPersonaRequest, redis: aioredis.Redis = Depends(get_redis)):
    session = PersonaSession(
        session_id=req.session_id,
        user_id=req.user_id,
        persona_id=req.persona_id,
        language=req.language,
        emotion_state=req.emotion_state,
        conversation_summary="",
        active_context_window=[],
        memory_refs=[]
    )
    await redis.set(f"persona:state:{req.session_id}", session.model_dump_json())
    return {"status": "loaded", "session": session}

@router.post("/switch")
async def switch_persona(req: SwitchPersonaRequest, redis: aioredis.Redis = Depends(get_redis)):
    state_raw = await redis.get(f"persona:state:{req.session_id}")
    if not state_raw:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = PersonaSession.model_validate_json(state_raw)
    session.persona_id = req.persona_id
    session.language = req.language
    await redis.set(f"persona:state:{req.session_id}", session.model_dump_json())
    return {"status": "switched", "session": session}

@router.get("/state")
async def get_state(session_id: str, redis: aioredis.Redis = Depends(get_redis)):
    state_raw = await redis.get(f"persona:state:{session_id}")
    if not state_raw:
        raise HTTPException(status_code=404, detail="Session not found")
    return PersonaSession.model_validate_json(state_raw)
