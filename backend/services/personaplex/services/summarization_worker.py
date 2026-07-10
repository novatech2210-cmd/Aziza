import asyncio
import json
import time
from datetime import datetime, timedelta
import structlog
from .vector_search import VectorMemoryStore

logger = structlog.get_logger()

class BackgroundSummarizer:
    def __init__(self, personaplex):
        self.personaplex = personaplex
        self.vector_store = VectorMemoryStore()
        self.is_running = False

    async def start(self):
        self.is_running = True
        asyncio.create_task(self._summarization_loop())

    async def _summarization_loop(self):
        logger.info("Summarization worker starting...")
        while self.is_running:
            try:
                await self._process_old_sessions()
                await asyncio.sleep(180)  # Run every 3 minutes
            except Exception as e:
                logger.error("Summarization worker error", error=str(e))
                await asyncio.sleep(30)

    async def _process_old_sessions(self):
        # Find sessions inactive > 10 minutes
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        
        # We query the meta hash in Redis or session docs in Mongo
        # For simplicity in 6B, we check Redis session TTLs or a separate registry
        pass

    async def _summarize_session(self, session_id: str, user_id: str):
        history = await self.personaplex.redis.redis.lrange(f"history:{session_id}", 0, -1)
        
        if len(history) < 5:
            return

        # Simple concatenation for now (LLM summarization would happen here)
        summary = f"Summary of session {session_id} with {len(history)} turns."
        
        # Store long-term memory
        await self.vector_store.add_memory(
            content=summary,
            metadata={
                "session_id": session_id,
                "user_id": user_id,
                "type": "conversation_summary"
            }
        )

        # Update hot cache
        await self.personaplex.redis.update_session_context(
            session_id, 
            {"conversation_summary": summary}
        )

        logger.info("Session summarized", session_id=session_id)
