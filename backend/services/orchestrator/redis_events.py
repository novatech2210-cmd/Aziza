import json
import asyncio
import structlog

logger = structlog.get_logger()

async def listen_to_redis(orchestrator):
    pubsub = orchestrator.redis.pubsub()
    await pubsub.psubscribe("gateway:connection", "session:*:control")
    
    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue
            
        channel = message["channel"]
        data = message["data"]
        
        if channel == "gateway:connection":
            await orchestrator._handle_connection(data)
        elif channel.endswith(":control"):
            try:
                msg = json.loads(data)
                if msg.get("action") == "interrupt":
                    session_id = channel.split(":")[1]
                    await orchestrator.trigger_interrupt(session_id)
            except:
                pass
