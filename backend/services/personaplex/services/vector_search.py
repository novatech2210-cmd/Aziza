from sentence_transformers import SentenceTransformer
import motor.motor_asyncio
from typing import List
from datetime import datetime
from ..config import settings

class VectorMemoryStore:
    def __init__(self):
        # We will initialize this lazily to avoid blocking startup
        self.embedder = None
        self.client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]

    def _ensure_embedder(self):
        if self.embedder is None:
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')

    async def add_memory(self, content: str, metadata: dict):
        self._ensure_embedder()
        embedding = self.embedder.encode(content).tolist()
        
        memory = {
            "content": content,
            "embedding": embedding,
            "metadata": metadata,
            "timestamp": datetime.utcnow()
        }
        await self.db.long_term_memory.insert_one(memory)

    async def semantic_search(self, query: str, limit: int = 5) -> List[dict]:
        self._ensure_embedder()
        query_embedding = self.embedder.encode(query).tolist()
        
        # Standard MongoDB vector search pipeline
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "queryVector": query_embedding,
                    "path": "embedding",
                    "limit": limit,
                    "numCandidates": limit * 4
                }
            },
            {"$project": {"content": 1, "metadata": 1, "score": {"$meta": "vectorSearchScore"}}}
        ]
        try:
            cursor = self.db.long_term_memory.aggregate(pipeline)
            return await cursor.to_list(length=limit)
        except Exception:
            # Fallback for local mongo without vector index
            cursor = self.db.long_term_memory.find({}, {"content": 1, "metadata": 1}).limit(limit)
            return await cursor.to_list(length=limit)
