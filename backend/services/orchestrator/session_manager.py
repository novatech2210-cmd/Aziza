import logging
import json
import httpx
import os
from datetime import datetime, timedelta

logger = logging.getLogger("SessionManager")

from state_machine import SessionContext, SessionState

# Session TTL (24 hours)
SESSION_TTL_SECONDS = 86400

class SessionManager:
    def __init__(self, redis_conn):
        self.redis = redis_conn
        self.sessions: dict[str, SessionContext] = {}
        self.persona_plex_url = os.getenv("PERSONA_PLEX_URL", "http://localhost:8000")

    async def ensure_session(self, session_id: str, params: dict = None):
        if session_id not in self.sessions:
            logger.info(f"Initializing new session: {session_id}")
            session = SessionContext(session_id)
            session.state = SessionState.LISTENING
            self.sessions[session_id] = session
            params = params or {}
            
            # Try to restore existing session from Redis
            existing_meta = await self.redis.hgetall(f"session:{session_id}:meta")
            if existing_meta and existing_meta.get("status") == "active":
                logger.info(f"Restoring existing session: {session_id}")
                session.text_prompt = existing_meta.get("text_prompt", "")
                session.voice_prompt = existing_meta.get("voice_prompt", "")
                # Update last activity
                await self.redis.hset(f"session:{session_id}:meta", "last_activity", datetime.utcnow().isoformat())
                return
            
            # Fetch context from PersonaPlex (optional fallback)
            context = {"history": []}
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"{self.persona_plex_url}/sessions/{session_id}/context")
                    if resp.status_code == 200:
                        context = resp.json()
                        logger.info(f"Context loaded for {session_id}")
            except Exception as e:
                logger.warning(f"Could not load context for {session_id}: {e}")

            # Merge connection params into metadata
            meta = {
                "status": "active",
                "context": json.dumps(context),
                "text_prompt": params.get("text_prompt", ""),
                "voice_prompt": params.get("voice_prompt", ""),
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
            }

            # Register session in Redis with TTL
            await self.redis.hset(f"session:{session_id}:meta", mapping=meta)
            await self.redis.expire(f"session:{session_id}:meta", SESSION_TTL_SECONDS)
            session.text_prompt = meta["text_prompt"]
            session.voice_prompt = meta["voice_prompt"]
            
            # Notify Moshi Runtime and Streaming Runtime
            start_event = {
                "sessionId": session_id,
                "text_prompt": meta["text_prompt"],
                "voice_prompt": meta["voice_prompt"],
            }
            await self.redis.publish("session:start", json.dumps(start_event))
            logger.info(f"Sent session:start for {session_id}")

    async def end_session(self, session_id: str):
        if session_id in self.sessions:
            logger.info(f"Ending session: {session_id}")
            await self.redis.hset(f"session:{session_id}:meta", "status", "ended")
            await self.redis.expire(f"session:{session_id}:meta", 300)  # Keep for 5 min for cleanup
            del self.sessions[session_id]
            await self.redis.publish("orchestrator:session_end", json.dumps({"session_id": session_id}))

    async def update_activity(self, session_id: str):
        """Update last activity timestamp for session TTL management."""
        if session_id in self.sessions:
            await self.redis.hset(f"session:{session_id}:meta", "last_activity", datetime.utcnow().isoformat())
            await self.redis.expire(f"session:{session_id}:meta", SESSION_TTL_SECONDS)

    async def get_session_history(self, session_id: str, limit: int = 50):
        """Retrieve conversation history for a session."""
        history_key = f"session:{session_id}:history"
        history = await self.redis.lrange(history_key, 0, limit - 1)
        return [json.loads(msg) for msg in history]

    async def add_to_history(self, session_id: str, role: str, content: str):
        """Add a message to session history."""
        history_key = f"session:{session_id}:history"
        message = json.dumps({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        await self.redis.rpush(history_key, message)
        # Trim history to last 100 messages
        await self.redis.ltrim(history_key, -100, -1)
        # Set TTL on history
        await self.redis.expire(history_key, SESSION_TTL_SECONDS)
