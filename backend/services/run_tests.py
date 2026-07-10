import asyncio
import websockets
import json
import uuid
import sys

async def test_moshi_chat():
    print("Testing /api/chat (Moshi voice/text gateway)")
    try:
        async with websockets.connect("ws://localhost:8080/api/chat") as websocket:
            # First handshake (3 bytes: 0x00, 0x00, 0x00)
            msg = await websocket.recv()
            print(f"Received handshake: {list(msg)}")
            
            # Send Ping
            await websocket.send(bytes([0x06]))
            pong = await websocket.recv()
            print(f"Received ping response: {list(pong)}")

            # Send Text-in (0x02)
            text_payload = b"Hello Moshi!"
            await websocket.send(bytes([0x02]) + text_payload)
            print("Sent Text: 'Hello Moshi!'")
            
            # Await response from Moshi
            try:
                # Wait for up to 5 seconds for a response
                while True:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"Received Response Type {resp[0]}: {resp[1:]}")
                    if resp[0] == 2:
                        print("Received text response.")
                        break
            except asyncio.TimeoutError:
                print("Timeout waiting for Moshi response. Moshi service might not be running or listening.")
                
            print("Moshi test completed.\n")
    except Exception as e:
        print(f"Moshi test failed: {e}\n")

async def test_text_chat():
    print("Testing /api/chat-text (Text-to-Text gateway)")
    try:
        async with websockets.connect("ws://localhost:8080/api/chat-text") as websocket:
            # Send text as JSON
            await websocket.send(json.dumps({"message": "What is 2+2?"}))
            print("Sent Text: 'What is 2+2?'")
            
            # Await response from Ollama
            try:
                # Wait for up to 10 seconds for a response
                while True:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(resp)
                    if data.get("type") == "token":
                        print(data.get("content", ""), end="", flush=True)
                    elif data.get("type") == "done":
                        print("\nReceived full text response.")
                        break
                    else:
                        print(f"Received JSON: {data}")
            except asyncio.TimeoutError:
                print("Timeout waiting for Ollama response.")
                
            print("Text test completed.\n")
    except Exception as e:
        print(f"Text test failed: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_moshi_chat())
    asyncio.run(test_text_chat())
