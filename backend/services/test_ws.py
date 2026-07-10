import asyncio
import websockets
import json

async def test_gateway():
    uri = "ws://localhost:8080/api/chat"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to Gateway!")
            # Send initial message to trigger assignment
            payload = json.dumps({"sessionId": "test-session-123"})
            await websocket.send(payload)
            print(f"Sent: {payload}")
            
            while True:
                response = await websocket.recv()
                print(f"Received: {response}")
                if "worker_assigned" in response:
                    break
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_gateway())
