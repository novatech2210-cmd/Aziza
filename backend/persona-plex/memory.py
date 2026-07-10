"""
Conversation Memory System for PersonaPlex.

Provides conversation history storage, retrieval, and context injection.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import json

logger = logging.getLogger("Memory")

# Memory retention settings
MAX_HISTORY_MESSAGES = 100
CONTEXT_WINDOW_MESSAGES = 10
MEMORY_TTL_DAYS = 30


class ConversationMemory:
    """Manages conversation history and context for sessions."""
    
    def __init__(self, redis_conn, mongo_db):
        self.redis = redis_conn
        self.db = mongo_db
        self.active_buffers: dict[str, list[dict]] = {}
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ):
        """
        Add a message to conversation history.
        
        Args:
            session_id: Session identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            metadata: Optional metadata (language, tokens, etc.)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
        }
        if metadata:
            message.update(metadata)
        
        # Add to Redis buffer for fast access
        buffer_key = f"session:{session_id}:messages"
        await self.redis.rpush(buffer_key, json.dumps(message))
        await self.redis.ltrim(buffer_key, -MAX_HISTORY_MESSAGES, -1)
        await self.redis.expire(buffer_key, 86400)  # 24h TTL
        
        # Add to MongoDB for persistent storage
        try:
            await self.db.conversations.insert_one(message)
        except Exception as e:
            logger.warning(f"Failed to persist message to MongoDB: {e}")
        
        logger.debug(f"Added message to {session_id}: {role}={content[:50]}...")
    
    async def get_history(
        self,
        session_id: str,
        limit: int = CONTEXT_WINDOW_MESSAGES,
        include_metadata: bool = False,
    ) -> list[dict]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            include_metadata: Whether to include metadata fields
            
        Returns:
            List of messages in chronological order
        """
        buffer_key = f"session:{session_id}:messages"
        messages_raw = await self.redis.lrange(buffer_key, -limit, -1)
        
        if not messages_raw:
            # Try MongoDB as fallback
            cursor = self.db.conversations.find(
                {"session_id": session_id}
            ).sort("timestamp", -1).limit(limit)
            messages_raw = [json.dumps(msg) async for msg in cursor]
        
        messages = []
        for msg_raw in reversed(messages_raw):
            try:
                msg = json.loads(msg_raw)
                if not include_metadata:
                    msg = {k: v for k, v in msg.items() if k in ("role", "content", "timestamp")}
                messages.append(msg)
            except json.JSONDecodeError:
                continue
        
        return messages
    
    async def get_context_prompt(self, session_id: str) -> str:
        """
        Build a context prompt from conversation history.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Formatted context string
        """
        history = await self.get_history(session_id, limit=CONTEXT_WINDOW_MESSAGES)
        
        if not history:
            return ""
        
        context_lines = ["Relevant conversation context:"]
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            context_lines.append(f"{role}: {msg['content'][:200]}")
        
        return "\n".join(context_lines)
    
    async def clear_session(self, session_id: str):
        """Clear all history for a session."""
        buffer_key = f"session:{session_id}:messages"
        await self.redis.delete(buffer_key)
        logger.info(f"Cleared history for session {session_id}")
    
    async def get_session_stats(self, session_id: str) -> dict:
        """Get statistics for a session."""
        buffer_key = f"session:{session_id}:messages"
        message_count = await self.redis.llen(buffer_key)
        
        return {
            "session_id": session_id,
            "message_count": message_count,
            "max_messages": MAX_HISTORY_MESSAGES,
        }


# Global instance
_memory_instance: Optional[ConversationMemory] = None


def get_memory(redis_conn=None, mongo_db=None) -> ConversationMemory:
    """Get or create the global memory instance."""
    global _memory_instance
    if _memory_instance is None and redis_conn and mongo_db:
        _memory_instance = ConversationMemory(redis_conn, mongo_db)
    return _memory_instance
