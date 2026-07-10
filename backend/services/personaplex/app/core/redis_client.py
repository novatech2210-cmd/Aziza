import os
import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

async def get_redis() -> aioredis.Redis:
    redis = await aioredis.from_url(REDIS_URL)
    return redis
