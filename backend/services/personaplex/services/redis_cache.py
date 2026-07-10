import redis.asyncio as redis
import json
from typing import Optional, Dict
from ..config import settings

class RedisCache:
    def __init__(self):
        self.redis = None

    async def connect(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get_session_context(self, session_id: str) -> Optional[Dict]:
        data = await self.redis.hgetall(f"session:{session_id}")
        if not data:
            return None
        return data

    async def update_session_context(self, session_id: str, data: Dict):
        await self.redis.hset(f"session:{session_id}", mapping=data)
        await self.redis.expire(f"session:{session_id}", settings.SESSION_TTL)

    async def store_conversation_turn(self, session_id: str, turn: Dict):
        await self.redis.rpush(f"history:{session_id}", json.dumps(turn))
        await self.redis.ltrim(f"history:{session_id}", -20, -1)  # Keep last 20 turns
