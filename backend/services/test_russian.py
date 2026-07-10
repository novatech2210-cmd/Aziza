import asyncio
import websockets
import json

async def test_russian():
    uri = "ws://localhost:8080/api/chat-text?sessionId=test-russian"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to Gateway!")
            # Wait for the "ready" message
            response = await websocket.recv()
            print(f"Received: {response}")
            
            # Send a Russian query
            query = "Привет! Как тебя зовут и что ты умеешь делать?"
            payload = json.dumps({"message": query, "language": "ru-RU"})
            await websocket.send(payload)
            print(f"Sent: {payload}")
            
            # Receive chunks
            print("Response: ", end='', flush=True)
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                if data.get("type") == "token":
                    print(data.get("content", data.get("text", "")), end='', flush=True)
                elif data.get("type") == "done":
                    print("\n[Turn Ended]")
                    break
    except Exception as e:
        print(f"\nError: {e}")

asyncio.run(test_russian())
