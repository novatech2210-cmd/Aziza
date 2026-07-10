import asyncio
import websockets
import json

async def test_gateway():
    uri = "ws://127.0.0.1:8080/api/chat-text"
    
    prompts = [
        {"language": "en", "message": "Hello, how are you?"},
        {"language": "uz_latin", "message": "Salom, qalaysiz?"},
        {"language": "ru", "message": "Привет, как дела?"}
    ]
    
    for p in prompts:
        print(f"\n--- Testing Language: {p['language']} ---")
        async with websockets.connect(uri) as websocket:
            # Wait for ready
            msg = await websocket.recv()
            print(f"Server: {msg}")
            
            # Send message
            payload = {
                "message": p["message"],
                "language": p["language"]
            }
            print(f"Sending: {payload}")
            await websocket.send(json.dumps(payload))
            
            # Receive response stream
            full_response = ""
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                if data.get("type") == "token":
                    full_response += data["content"]
                elif data.get("type") == "done":
                    break
                elif data.get("type") == "error":
                    print(f"Error from gateway: {data.get('message')}")
                    break
            
            print(f"Response: {full_response}")

asyncio.run(test_gateway())
