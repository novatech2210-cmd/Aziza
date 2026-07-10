import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/aziza")

async def get_mongo() -> AsyncIOMotorClient:
    client = AsyncIOMotorClient(MONGO_URL)
    return client.aziza
