import asyncio
import json
import redis.asyncio as redis

async def main():
    session_id = "test_smoke_bilingual"
    r = redis.Redis(host='localhost', port=6379, decode_responses=False)
    
    pubsub = r.pubsub()
    await pubsub.subscribe(f"session:{session_id}:tokens")
    
    payload = {
        "session_id": session_id,
        "text": "Привет! Как дела?",
        "language": "ru"
    }
    
    # Wait for subscription
    await asyncio.sleep(0.5)
    
    # Publish to queue
    await r.rpush("aziza:text_in:queue", json.dumps(payload))
    print(f"Sent text prompt: {payload['text']}")
    
    print("Waiting for response...")
    response_tokens = []
    
    try:
        async with asyncio.timeout(30):
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    token = msg["data"].decode('utf-8')
                    response_tokens.append(token)
                    print(f"Token: {token}")
                    
                    # If we get enough tokens, break (since streaming might keep going)
                    if len(response_tokens) > 10:
                        break
    except asyncio.TimeoutError:
        print("Timeout waiting for response.")
        
    full_response = "".join(response_tokens)
    print(f"\nFinal Response Snippet: {full_response}")
    
    if any("\u0400" <= c <= "\u04FF" for c in full_response):
        print("✅ SUCCESS: Response contains Cyrillic (Russian) text!")
    else:
        print("❌ WARNING: No Russian characters detected in response.")
        
    await pubsub.unsubscribe()
    await r.close()

if __name__ == "__main__":
    asyncio.run(main())
