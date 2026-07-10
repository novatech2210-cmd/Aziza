from .redis_cache import RedisCache
from .mongo_store import MongoStore
from .vector_search import VectorMemoryStore
from ..models.schema import EmotionalState
import time
import json
import structlog

logger = structlog.get_logger()

class PersonaPlexService:
    def __init__(self):
        self.redis = RedisCache()
        self.mongo = MongoStore()
        self.vector_store = VectorMemoryStore()

    async def startup(self):
        await self.redis.connect()

    async def build_prompt(self, session_id: str, user_message: str) -> str:
        """Ultra-fast hot path - must stay under 30ms"""
        start = time.perf_counter()

        # 1. Get hot context from Redis
        context = await self.redis.get_session_context(session_id) or {}

        # 2. Get base persona (cached in Redis if possible)
        persona = context.get("persona_prompt") or "You are a helpful, professional assistant."

        # 3. Recent conversation
        recent = await self.redis.redis.lrange(f"history:{session_id}", -10, -1)  # last 10 turns

        history_str = "\n".join([json.loads(t)["user"] + ": " + json.loads(t)["assistant"] for t in recent]) if recent else ""

        # 4. Build final prompt
        prompt = f"""{persona}

<conversation_summary>
{context.get('conversation_summary', 'No prior summary.')}
</conversation_summary>

<recent_history>
{history_str}
</recent_history>

User: {user_message}

Assistant:"""

        latency_ms = (time.perf_counter() - start) * 1000
        if latency_ms > 25:
            logger.warning("Slow prompt assembly", latency=latency_ms, session_id=session_id)

        return prompt

    async def update_after_turn(self, session_id: str, user_message: str, assistant_response: str, emotion: str = "neutral"):
        """Update hot cache after each exchange"""
        turn = {
            "user": user_message,
            "assistant": assistant_response,
            "timestamp": time.time()
        }
        await self.redis.store_conversation_turn(session_id, turn)

        # Light summary update
        await self.redis.update_session_context(session_id, {
            "last_emotion": emotion,
            "last_updated": str(time.time())
        })

    async def get_relevant_memories(self, query: str, session_id: str) -> str:
        """Semantic recall for prompt enrichment"""
        memories = await self.vector_store.semantic_search(query, limit=4)
        if not memories:
            return ""
        return "\n".join([m["content"] for m in memories])

    async def update_emotional_state(self, session_id: str, new_emotion: EmotionalState):
        await self.redis.update_session_context(session_id, {
            "emotion_state": json.dumps(new_emotion.dict())
        })

    async def evolve_persona(self, persona_id: str, interaction_feedback: dict):
        # Simple trait adaptation logic (expand as needed)
        pass
