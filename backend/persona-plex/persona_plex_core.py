import time
import logging
import json
import redis.asyncio as redis

logger = logging.getLogger("PersonaPlexCore")

PERSONA_TEMPLATES = {
    "ru": "Ты Азиза — тёплый, умный AI-помощник. Говори естественно по-русски.",
    "uz-latn": "Siz Aziza — mehribon, aqlli AI yordamchisiz. O'zbek tilida gapiring.",
    "uz-cyrl": "Сиз Азиза — меҳрибон, ақлли AI ёрдамчисисиз. Ўзбек тилида гапиринг.",
    "en": "You are Aziza — a warm, intelligent AI assistant."
}

class StreamingSafePersonaPlex:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_conn = None

    async def connect(self):
        if not self.redis_conn:
            self.redis_conn = redis.from_url(self.redis_url)

    async def load_persona(self, session_id: str, persona_id: str, language: str, emotion_state: str):
        await self.connect()
        state = {
            "persona_id": persona_id,
            "language": language,
            "emotion_state": emotion_state
        }
        await self.redis_conn.hset(f"persona:state:{session_id}", mapping=state)
        # Seed hot cache
        prompt = self._assemble_prompt(language, emotion_state)
        await self.redis_conn.set(f"persona:context:{session_id}", prompt)

    async def switch_persona(self, session_id: str, persona_id: str = None, language: str = None, emotion_state: str = None):
        await self.connect()
        state_key = f"persona:state:{session_id}"
        
        current_state = await self.redis_conn.hgetall(state_key)
        if not current_state:
            current_state = {b"persona_id": b"default", b"language": b"en", b"emotion_state": b"neutral"}

        updates = {}
        if persona_id: updates["persona_id"] = persona_id
        if language: updates["language"] = language
        if emotion_state: updates["emotion_state"] = emotion_state
        
        if updates:
            await self.redis_conn.hset(state_key, mapping=updates)
            
        # Re-fetch state for assembly
        current_state = await self.redis_conn.hgetall(state_key)
        lang = current_state.get(b"language", b"en").decode()
        emotion = current_state.get(b"emotion_state", b"neutral").decode()

        prompt = self._assemble_prompt(lang, emotion)
        await self.redis_conn.set(f"persona:context:{session_id}", prompt)

    async def get_state(self, session_id: str) -> dict:
        await self.connect()
        state = await self.redis_conn.hgetall(f"persona:state:{session_id}")
        return {k.decode(): v.decode() for k, v in state.items()}

    def _assemble_prompt(self, language: str, emotion_state: str) -> str:
        base_template = PERSONA_TEMPLATES.get(language, PERSONA_TEMPLATES["en"])
        return f"{base_template} [Emotion: {emotion_state}]"

    async def build_prompt(self, session_id: str, user_message: str = "") -> str:
        """
        Hot path — Redis only. Target latency < 30ms.
        """
        start = time.perf_counter()
        await self.connect()

        # Fetch session context from Redis
        context = await self.redis_conn.get(f"persona:context:{session_id}")
        
        persona = context.decode() if context else PERSONA_TEMPLATES["en"]
        
        # Simple assembly
        if user_message:
            prompt = f"Persona: {persona}\nUser: {user_message}\nAssistant:"
        else:
            prompt = persona

        latency = (time.perf_counter() - start) * 1000
        if latency > 30:
            logger.warning(f"Prompt assembly slow: {latency:.1f}ms")
        
        return prompt

    async def update_hot_cache(self, session_id: str, new_data: dict):
        await self.connect()
        await self.redis_conn.hset(f"session:{session_id}:meta", mapping=new_data)
