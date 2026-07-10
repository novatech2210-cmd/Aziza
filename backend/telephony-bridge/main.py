import base64
import json
import logging
import os
import audioop
import asyncio
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelephonyBridge")

app = FastAPI()
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

@app.post("/twiml")
async def get_twiml(request: Request):
    """Returns TwiML to start the media stream."""
    host = request.headers.get("host")
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/twiml/stream" />
    </Connect>
</Response>"""
    return Response(content=response_xml, media_type="application/xml")

@app.websocket("/twiml/stream")
async def handle_twilio_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Twilio WebSocket connected")
    
    r = redis.from_url(redis_url)
    stream_sid = None
    session_id = None
    
    # Task to handle playback from Redis to Twilio
    playback_task = None

    async def playback_loop(sid, sess_id):
        pubsub = r.pubsub()
        await pubsub.subscribe(f"session:{sess_id}:playback")
        async for message in pubsub.listen():
            if message["type"] == "message":
                audio_data = message["data"]
                # Convert 16kHz linear PCM to 8kHz mulaw
                # Resample: 16k -> 8k
                audio_8k, _ = audioop.ratecv(audio_data, 2, 1, 16000, 8000, None)
                # Convert to mulaw
                mulaw_data = audioop.lin2ulaw(audio_8k, 2)
                # Base64 encode
                payload = base64.b64encode(mulaw_data).decode("utf-8")
                
                await websocket.send_json({
                    "event": "media",
                    "streamSid": sid,
                    "media": {
                        "payload": payload
                    }
                })

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event")
            
            if event == "start":
                stream_sid = data["start"]["streamSid"]
                session_id = f"twilio_{stream_sid}"
                logger.info(f"Stream started: {stream_sid}, Session: {session_id}")
                
                # Start playback listener
                playback_task = asyncio.create_task(playback_loop(stream_sid, session_id))
                
            elif event == "media":
                if not session_id:
                    continue
                
                # Decode Twilio audio (mulaw 8kHz)
                payload = data["media"]["payload"]
                mulaw_data = base64.b64decode(payload)
                
                # Convert mulaw to linear PCM
                linear_data = audioop.ulaw2lin(mulaw_data, 2)
                
                # Upsample: 8k -> 16k
                audio_16k, _ = audioop.ratecv(linear_data, 2, 1, 8000, 16000, None)
                
                # Publish to Redis for Streaming Runtime
                await r.publish(f"session:{session_id}:audio_in", audio_16k)
                
            elif event == "stop":
                logger.info(f"Stream stopped: {stream_sid}")
                break
                
    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")
    finally:
        if playback_task:
            playback_task.cancel()
        await r.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
