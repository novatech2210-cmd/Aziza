import asyncio
import websockets
import json
import sys

async def test_russian(query):
    uri = "ws://localhost:8080/api/chat-text?sessionId=test-russian-2"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.recv()
            payload = json.dumps({"message": query})
            await websocket.send(payload)
            print(f"Sent: {query}")
            print("Response: ", end='', flush=True)
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                if data.get("type") == "token":
                    print(data.get("content", ""), end='', flush=True)
                elif data.get("type") == "done":
                    print("\n[Turn Ended]\n")
                    break
    except Exception as e:
        print(f"\nError: {e}")

async def main():
    prompts = [
        "Извинись за свою ошибку.",
        "Расскажи мне шутку про программистов.",
        "Ты умеешь говорить по-английски?"
    ]
    for p in prompts:
        await test_russian(p)

asyncio.run(main())
