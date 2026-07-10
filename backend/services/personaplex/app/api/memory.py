from fastapi import APIRouter, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.mongo_client import get_mongo
from datetime import datetime

router = APIRouter()

class MemoryStoreRequest(BaseModel):
    user_id: str
    session_id: str
    summary: str

class MemoryRetrieveRequest(BaseModel):
    user_id: str
    limit: int = 5

@router.post("/store")
async def store_memory(req: MemoryStoreRequest, mongo: AsyncIOMotorClient = Depends(get_mongo)):
    memory_doc = {
        "user_id": req.user_id,
        "session_id": req.session_id,
        "summary": req.summary,
        "created_at": datetime.utcnow()
    }
    result = await mongo.memories.insert_one(memory_doc)
    return {"status": "stored", "memory_id": str(result.inserted_id)}

@router.post("/retrieve")
async def retrieve_memory(req: MemoryRetrieveRequest, mongo: AsyncIOMotorClient = Depends(get_mongo)):
    memories = await mongo.memories.find(
        {"user_id": req.user_id},
        {"_id": 1, "summary": 1, "created_at": 1}
    ).sort("created_at", -1).limit(req.limit).to_list(req.limit)
    
    # Convert ObjectIds to strings
    for m in memories:
        m["_id"] = str(m["_id"])
        
    return {"memories": memories}
