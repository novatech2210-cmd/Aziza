"""
Conversation Memory System for PersonaPlex.

Provides conversation history storage, retrieval, and context injection
with token-aware context window management.
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

# Token budget for context window (approximate: 1 token ~= 4 chars for English,
# ~2 chars for CJK, ~6 chars for Cyrillic). Use conservative estimate.
MAX_CONTEXT_TOKENS = 2000
CHARS_PER_TOKEN = 4  # Conservative estimate


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text (approximate)."""
    return len(text) // CHARS_PER_TOKEN + 1


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
            "token_count": _estimate_tokens(content),
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
        Build a context prompt from conversation history with token budget.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Formatted context string within token budget
        """
        # Get messages starting with most recent, within token budget
        buffer_key = f"session:{session_id}:messages"
        messages_raw = await self.redis.lrange(buffer_key, -CONTEXT_WINDOW_MESSAGES * 2, -1)
        
        if not messages_raw:
            return ""
        
        context_lines = []
        total_tokens = 0
        included_count = 0
        
        # Process from most recent backwards
        for msg_raw in reversed(messages_raw):
            try:
                msg = json.loads(msg_raw)
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                
                # Truncate long messages
                if len(content) > 200:
                    content = content[:200] + "..."
                
                line = f"{role}: {content}"
                line_tokens = _estimate_tokens(line)
                
                # Check token budget
                if total_tokens + line_tokens > MAX_CONTEXT_TOKENS:
                    break
                
                context_lines.insert(0, line)  # Insert at beginning for chronological order
                total_tokens += line_tokens
                included_count += 1
            except json.JSONDecodeError:
                continue
        
        if not context_lines:
            return ""
        
        header = f"Relevant conversation context ({included_count} recent messages):"
        return header + "\n" + "\n".join(context_lines)
    
    async def get_context_summary(self, session_id: str) -> dict:
        """
        Get a summary of the conversation context.
        
        Returns:
            Dict with message count, token estimate, time span, etc.
        """
        buffer_key = f"session:{session_id}:messages"
        message_count = await self.redis.llen(buffer_key)
        
        if message_count == 0:
            return {
                "session_id": session_id,
                "message_count": 0,
                "total_tokens": 0,
                "time_span": None,
            }
        
        # Get first and last message timestamps
        first_raw = await self.redis.lindex(buffer_key, 0)
        last_raw = await self.redis.lindex(buffer_key, -1)
        
        first_ts = None
        last_ts = None
        total_tokens = 0
        
        if first_raw:
            try:
                first_msg = json.loads(first_raw)
                first_ts = first_msg.get("timestamp")
            except json.JSONDecodeError:
                pass
        
        if last_raw:
            try:
                last_msg = json.loads(last_raw)
                last_ts = last_msg.get("timestamp")
            except json.JSONDecodeError:
                pass
        
        # Estimate total tokens from recent messages
        recent = await self.redis.lrange(buffer_key, -20, -1)
        for msg_raw in recent:
            try:
                msg = json.loads(msg_raw)
                total_tokens += _estimate_tokens(msg.get("content", ""))
            except json.JSONDecodeError:
                pass
        
        return {
            "session_id": session_id,
            "message_count": message_count,
            "total_tokens": total_tokens,
            "first_message": first_ts,
            "last_message": last_ts,
            "max_messages": MAX_HISTORY_MESSAGES,
            "context_window_tokens": MAX_CONTEXT_TOKENS,
        }
    
    async def clear_session(self, session_id: str):
        """Clear all history for a session."""
        buffer_key = f"session:{session_id}:messages"
        await self.redis.delete(buffer_key)
        logger.info(f"Cleared history for session {session_id}")
    
    async def get_session_stats(self, session_id: str) -> dict:
        """Get statistics for a session."""
        summary = await self.get_context_summary(session_id)
        return {
            "session_id": session_id,
            "message_count": summary["message_count"],
            "total_tokens": summary["total_tokens"],
            "max_messages": MAX_HISTORY_MESSAGES,
        }


# Global instance
_memory_instance: Optional[ConversationMemory] = None


def get_memory(redis_conn=None, mongo_db=None) -> ConversationMemory:
    """Get or create the global memory instance."""
    global _memory_instance
    if _memory_instance is None and redis_conn is not None and mongo_db is not None:
        _memory_instance = ConversationMemory(redis_conn, mongo_db)
    return _memory_instance
