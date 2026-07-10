from fastapi import APIRouter, Depends
import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.redis_client import get_redis
from app.core.mongo_client import get_mongo
from app.models.session import PersonaSession
import json

router = APIRouter()

PERSONA_TEMPLATES = {
    "ru": (
        "Ты Азиза — тёплый, умный и внимательный AI-ассистент. "
        "Говори естественно по-русски, как живой человек. "
        "Избегай формальных оборотов. Отвечай кратко и по делу. "
        "Текущее эмоциональное состояние: {emotion_state}. "
        "Контекст разговора: {summary}"
    ),
    "uz-latn": (
        "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz. "
        "O'zbek tilida tabiiy va jonli gapiring. "
        "Qisqa va aniq javob bering. "
        "Hozirgi kayfiyat: {emotion_state}. "
        "Suhbat konteksti: {summary}"
    ),
    "uz-cyrl": (
        "Сиз Азиза — меҳрибон, ақлли ва диққатли AI ёрдамчисисиз. "
        "Ўзбек тилида табиий ва жонли гапиринг. "
        "Қисқа ва аниқ жавоб беринг. "
        "Ҳозирги кайфият: {emotion_state}. "
        "Суҳбат контексти: {summary}"
    ),
    "en": (
        "You are Aziza — a warm, intelligent, and attentive AI assistant. "
        "Speak naturally and conversationally. Keep responses concise. "
        "Current emotional state: {emotion_state}. "
        "Conversation context: {summary}"
    ),
}

@router.post("/build")
async def build_prompt(session_id: str, redis: aioredis.Redis = Depends(get_redis), mongo: AsyncIOMotorClient = Depends(get_mongo)):
    # 1. Try Redis hot cache first (must be <5ms)
    cached = await redis.get(f"persona:context:{session_id}")
    if cached:
        return {"prompt": cached.decode()}

    # 2. Cache miss — build from state + memory
    state_raw = await redis.get(f"persona:state:{session_id}")
    if not state_raw:
        return {"error": "Session state not found"}
        
    state = PersonaSession.model_validate_json(state_raw)

    # 3. Retrieve relevant memories from MongoDB (limit to 3, sorted by relevance)
    memories = await mongo.memories.find(
        {"user_id": state.user_id},
        {"summary": 1},
        sort=[("created_at", -1)],
        limit=3
    ).to_list(3)
    memory_context = " ".join(m.get("summary", "") for m in memories)

    # 4. Assemble prompt
    template = PERSONA_TEMPLATES.get(state.language, PERSONA_TEMPLATES["en"])
    prompt = template.format(
        emotion_state=state.emotion_state,
        summary=f"{state.conversation_summary} {memory_context}".strip()
    )

    # 5. Cache assembled prompt with 60s TTL
    await redis.setex(f"persona:context:{session_id}", 60, prompt)
    return {"prompt": prompt}
