import motor.motor_asyncio
from datetime import datetime
from ..config import settings

class MongoStore:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]

    async def save_persona(self, persona: dict):
        await self.db.personas.update_one(
            {"persona_id": persona["persona_id"]},
            {"$set": persona},
            upsert=True
        )

    async def get_persona(self, persona_id: str):
        return await self.db.personas.find_one({"persona_id": persona_id})

    async def save_long_term_memory(self, user_id: str, memory: dict):
        memory["timestamp"] = datetime.utcnow()
        await self.db.long_term_memory.insert_one(memory)
