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
from memory import ConversationMemory, get_memory
from emotion import detect_emotion, get_emotion_adaptation, get_emotion_state, EmotionResult
from structured_logging import setup_structured_logging, set_session_id, set_user_id

# Setup structured JSON logging
setup_structured_logging("personaplex", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("PersonaPlex")

app = FastAPI(title="Aziza PersonaPlex")
from fastapi.responses import HTMLResponse
@app.get("/aziza-personaplex-test.html", response_class=HTMLResponse)
async def get_test_page():
    with open("/root/aziza-build/aziza-personaplex-test.html", "r") as f:
        return f.read()

redis_conn = None
plex_core = None
memory: ConversationMemory = None

@app.on_event("startup")
async def startup():
    global redis_conn, plex_core, memory
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = redis.from_url(redis_url)
    plex_core = StreamingSafePersonaPlex(redis_url=redis_url)
    await plex_core.connect()
    
    # Initialize ConversationMemory (Redis + MongoDB)
    memory = get_memory(redis_conn=redis_conn, mongo_db=db)
    logger.info("PersonaPlex connected to Redis, ConversationMemory initialized")
    
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
            if content and memory:
                logger.debug(f"Saving memory for {session_id}: {content[:80]}...")
                await memory.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    metadata={"source": "token_aggregation"},
                )
            session_buffers[session_id] = ""

@app.get("/sessions/{session_id}/context")
async def get_context(session_id: str):
    history = await get_session_history(session_id)
    return {"session_id": session_id, "history": history}

@app.post("/personas")
async def create_persona(persona: Persona):
    data = persona.dict(by_alias=True)
    await db.personas.update_one(
        {"_id": data["_id"]},
        {"$set": data},
        upsert=True,
    )
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
    # Build base prompt from persona
    prompt = await plex_core.build_prompt(req.session_id, req.user_message)
    
    # Detect emotion and adapt persona if user message provided
    emotion_result = None
    if req.user_message:
        # Get session language for emotion detection
        state = await plex_core.get_state(req.session_id)
        language = state.get("language", "en")
        
        emotion_result = detect_emotion(req.user_message, language)
        
        # Store emotion in session history
        emotion_key = f"session:{req.session_id}:emotions"
        await redis_conn.rpush(emotion_key, emotion_result.emotion)
        await redis_conn.ltrim(emotion_key, -20, -1)  # Keep last 20 emotions
        await redis_conn.expire(emotion_key, 86400)
        
        # Get dominant emotion from recent history
        recent_emotions = await redis_conn.lrange(emotion_key, -5, -1)
        if recent_emotions:
            dominant = get_emotion_state([e.decode() for e in recent_emotions])
            adaptation = get_emotion_adaptation(dominant)
            if adaptation:
                prompt = f"{adaptation}\n\n{prompt}"
        
        # Record user message to conversation history
        if memory:
            await memory.add_message(
                session_id=req.session_id,
                role="user",
                content=req.user_message,
                metadata={"emotion": emotion_result.emotion, "emotion_confidence": emotion_result.confidence},
            )
    
    # Inject conversation context if available
    if memory and req.user_message:
        context = await memory.get_context_prompt(req.session_id)
        if context:
            prompt = f"{context}\n\n{prompt}"
    
    response = {"prompt": prompt}
    if emotion_result:
        response["emotion"] = {
            "detected": emotion_result.emotion,
            "confidence": emotion_result.confidence,
            "arousal": emotion_result.arousal,
            "valence": emotion_result.valence,
        }
    return response

from pydantic import BaseModel
class LangDetectRequest(BaseModel):
    text: str

# Unicode ranges for script detection
_CYRILLIC_RANGE = (0x0400, 0x04FF)  # Basic Cyrillic
_CYRILLIC_EXT_RANGE = (0x0500, 0x052F)  # Cyrillic Supplement
_LATIN_RANGE = (0x0041, 0x007A)  # Basic Latin a-z/A-Z

def _count_script_chars(text: str) -> dict[str, int]:
    """Count characters by script for reliable language detection."""
    counts = {"cyrillic": 0, "latin": 0, "other": 0}
    for ch in text:
        cp = ord(ch)
        if (_CYRILLIC_RANGE[0] <= cp <= _CYRILLIC_RANGE[1] or
                _CYRILLIC_EXT_RANGE[0] <= cp <= _CYRILLIC_EXT_RANGE[1]):
            counts["cyrillic"] += 1
        elif _LATIN_RANGE[0] <= cp <= _LATIN_RANGE[1]:
            counts["latin"] += 1
        elif ch.isalpha():
            counts["other"] += 1
    return counts

# Uzbek-specific words (common greetings, pronouns, particles) for disambiguation
# Expanded with transliterated forms users commonly type in Latin script
_UZBEK_LATIN_INDICATORS = {
    # Pronouns & determiners
    "siz", "biz", "men", "sen", "uning", "ular", "bizning",
    "mening", "sening", "sizning", "ularning", "shu", "bu",
    # Conjunctions & particles
    "va", "lekin", "yoki", "ham", "garchi", "shuningdek",
    "balki", "yoqsa", "agarda", "agar",
    # Postpositions
    "da", "dan", "ga", "ni", "uchtun", "ustida", "ostida",
    "oldida", "keyinida", "yonida", "orasida",
    # Question words
    "qanday", "nima", "qachon", "qaerda", "nega", "qanaqa",
    "necha", "qaysi", "nimani", "qayerdan",
    # Common verbs & adjectives
    "yaxshi", "yomon", "katta", "kichik", "yangi", "eski",
    "chiroyli", "tez", "sekin", "kerak", "mumkin",
    # Greetings & politeness
    "salom", "assalomu", "alaykum", "rahmat", "kechirasiz",
    "iltimos", "xush", "kelibsiz", "hayr",
    # Numbers
    "bir", "ikki", "uch", "besh", "olti", "yetti",
    # Common nouns
    "odam", "joy", "vaqt", "kun", "oy", "yil", "soat",
    "mamlakat", "shahar", "maktab", "ish",
    # Affixes that are strong Uzbek signals
    "lish", "mish", "dir", "kan", "mikan", "echan", "uvchi",
    # Transliterated forms users often type
    "qalesiz", "qalaysiz", "yaxshimisiz", "menga", "senga",
    "unga", "bizga", "ulgarga", "meni", "seni", "sizni",
    # Uzbek-specific Latin letters as strong signal
    "o'g", "o'z",
}

_UZBEK_CYRILLIC_INDICATORS = {
    # Pronouns
    "сиз", "биз", "мен", "сен", "уния", "улар",
    "менинг", "сенинг", "сизнинг", "бизнинг", "уларнинг",
    # Conjunctions
    "ва", "лекин", "ёки", "ҳам", "гарчи", "шунингдек",
    "агар", "агарда",
    # Question words
    "қандай", "нима", "қачон", "қаерда", "нега", "қанақа",
    "неча", "қайси", "нимани", "қаердан",
    # Common words
    "яхши", "ёмон", "бор", "йўқ", "қилиш", "бўлиш",
    "керак", "мумкин", "тушунди",
    # Greetings
    "салом", "ассалому", "алайкум", "раҳмат", "кечирингиз",
    "илтимос", "ҳайр",
    # Numbers
    "бир", "икки", "уч", "тўрт", "беш",
    # Common nouns
    "одам", "жой", "вақт", "кун", "ой", "йил",
    "шаҳар", "мактаб", "иш",
    # Affixes
    "лиш", "миш", "дир", "кан", "микан",
}

# Transliterated Uzbek words that users commonly type in Latin script
# These overlap with English characters but signal Uzbek intent
_TRANSLITERATED_UZ_INDICATORS = {
    "assalomu", "alaykum", "rahmat", "kechirasiz", "iltimos",
    "yaxshimisiz", "qalaysiz", "qalesiz",
    "yaxshi", "yomon", "katta", "kichik", "yangi", "eski",
    "qanday", "qachon", "qaerda", "nega", "qanaqa",
    "salom", "hayr", "xush", "kelibsiz",
    "menga", "senga", "unga", "bizga", "ulgarga",
    "meni", "seni", "sizni", "uni", "bizni", "уларни",
    "shuning", "uning", "bizning",
}

@app.post("/lang/detect")
async def detect_lang(req: LangDetectRequest):
    text = req.text.strip()
    if not text:
        return {"language": "en", "confidence": 0.0}

    counts = _count_script_chars(text)
    total_alpha = counts["cyrillic"] + counts["latin"] + counts["other"]

    if total_alpha == 0:
        return {"language": "en", "confidence": 0.0}

    cyrillic_ratio = counts["cyrillic"] / total_alpha
    latin_ratio = counts["latin"] / total_alpha

    # Pure Latin script → check for Uzbek indicators
    if latin_ratio > 0.8 and cyrillic_ratio < 0.05:
        words = set(req.text.lower().split())
        uz_overlap = words & _UZBEK_LATIN_INDICATORS
        transliterated_overlap = words & _TRANSLITERATED_UZ_INDICATORS
        total_uz = len(uz_overlap) + len(transliterated_overlap)
        if total_uz >= 2:
            return {"language": "uz", "script": "latin", "confidence": 0.9}
        if total_uz >= 1 and latin_ratio > 0.9:
            # Single transliterated word in otherwise Latin text → likely Uzbek
            return {"language": "uz", "script": "latin", "confidence": 0.75}
        return {"language": "en", "confidence": 0.8}

    # Strong Cyrillic → check for Uzbek Cyrillic vs Russian
    if cyrillic_ratio > 0.7:
        words = set(req.text.lower().split())
        uz_cyrl_overlap = words & _UZBEK_CYRILLIC_INDICATORS
        if len(uz_cyrl_overlap) >= 2:
            return {"language": "uz", "script": "cyrillic", "confidence": 0.85}
        return {"language": "ru", "confidence": 0.9}

    # Mixed script → likely transliterated Uzbek or code-switching
    if cyrillic_ratio > 0.2 and latin_ratio > 0.2:
        words = set(req.text.lower().split())
        uz_overlap = (words & _UZBEK_LATIN_INDICATORS) | (words & _UZBEK_CYRILLIC_INDICATORS)
        transliterated_overlap = words & _TRANSLITERATED_UZ_INDICATORS
        total_uz = len(uz_overlap) + len(transliterated_overlap)
        if total_uz >= 2:
            return {"language": "uz", "script": "mixed", "confidence": 0.7}

    # Default: Cyrillic → Russian, Latin → English
    if cyrillic_ratio > latin_ratio:
        return {"language": "ru", "confidence": max(0.6, cyrillic_ratio)}
    return {"language": "en", "confidence": max(0.6, latin_ratio)}

@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/sessions/{session_id}/history")
async def get_conversation_history(session_id: str, limit: int = 50):
    """Get conversation history for a session."""
    if not memory:
        return {"session_id": session_id, "messages": []}
    messages = await memory.get_history(session_id, limit=limit)
    return {"session_id": session_id, "messages": messages}


@app.post("/sessions/{session_id}/message")
async def record_message(session_id: str, req: LangDetectRequest):
    """Record a user message to conversation history."""
    if not memory:
        return {"status": "ok"}
    await memory.add_message(
        session_id=session_id,
        role="user",
        content=req.text,
    )
    return {"status": "ok"}


@app.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get session statistics."""
    if not memory:
        return {"session_id": session_id, "message_count": 0}
    stats = await memory.get_session_stats(session_id)
    
    # Add emotion stats
    emotion_key = f"session:{session_id}:emotions"
    recent_emotions = await redis_conn.lrange(emotion_key, -20, -1)
    if recent_emotions:
        emotion_list = [e.decode() for e in recent_emotions]
        stats["dominant_emotion"] = get_emotion_state(emotion_list)
        stats["emotion_history"] = emotion_list[-10:]
    
    return stats


@app.post("/emotion/detect")
async def detect_emotion_endpoint(req: LangDetectRequest, language: str = "en"):
    """Detect emotion from text. Optional query param `language` (en/ru/uz) for language-aware detection."""
    result = detect_emotion(req.text, language)
    return {
        "emotion": result.emotion,
        "confidence": result.confidence,
        "arousal": result.arousal,
        "valence": result.valence,
    }
