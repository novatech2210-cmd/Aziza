import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "aziza")

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

async def get_persona(persona_id: str):
    return await db.personas.find_one({"_id": persona_id})

async def save_memory(entry: dict):
    return await db.memories.insert_one(entry)

async def get_session_history(session_id: str, limit: int = 10):
    cursor = db.memories.find({"session_id": session_id}).sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc['_id'] = str(doc['_id'])
    return docs
