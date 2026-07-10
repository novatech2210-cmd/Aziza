import asyncio
import time
import json
import redis.asyncio as redis
import os

async def test_ttft():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = redis.from_url(redis_url)
    
    session_id = "test_ttft_session"
    
    # 1. Listen for playback audio or tokens
    pubsub = r.pubsub()
    await pubsub.subscribe(f"session:{session_id}:playback", f"session:{session_id}:tokens")
    
    # 2. Start session
    start_msg = {
        "sessionId": session_id,
        "text_prompt": "You are Aziza. Say 'hello'.",
        "voice_prompt": None
    }
    await r.publish("session:start", json.dumps(start_msg))
    
    # 3. Simulate text input to prompt generation
    text_in = "Hello Aziza, how are you today?"
    print(f"Sending prompt: '{text_in}'")
    start_time = time.perf_counter()
    
    # Assign worker
    await r.publish("orchestrator:session:assign:worker-01", session_id)
    # Send text
    await r.publish(f"session:{session_id}:text_in", text_in.encode('utf-8'))
    
    print("Waiting for response...")
    ttft = None
    
    try:
        async with asyncio.timeout(10.0):
            async for message in pubsub.listen():
                if message["type"] == "message":
                    end_time = time.perf_counter()
                    ttft = (end_time - start_time) * 1000
                    channel = message["channel"].decode('utf-8')
                    if "playback" in channel:
                        print(f"[Audio] TTFT: {ttft:.2f}ms")
                    else:
                        print(f"[Text] TTFT: {ttft:.2f}ms. Token: {message['data'].decode('utf-8')}")
                    break
    except asyncio.TimeoutError:
        print("Timeout waiting for response.")
        
    await r.publish(f"session:{session_id}:control", json.dumps({"action": "stop_audio"}))
    await r.close()

if __name__ == "__main__":
    asyncio.run(test_ttft())
