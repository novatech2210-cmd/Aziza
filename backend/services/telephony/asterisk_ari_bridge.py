import asyncio
import json
import os
import logging
import websockets
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AsteriskBridge")

ARI_URL = os.getenv("ARI_URL", "http://localhost:8088/ari")
ARI_WS_URL = os.getenv("ARI_WS_URL", "ws://localhost:8088/ari/events")
ARI_APP = "aziza"
ARI_USER = os.getenv("ARI_USER", "asterisk")
ARI_PASS = os.getenv("ARI_PASS", "asterisk")
GATEWAY_URL = os.getenv("GATEWAY_URL", "ws://localhost:3000/api/chat")

ACTIVE_CALLS = {}
PORT_COUNTER = 10000

class RTPBridge:
    """FFmpeg pipeline: RTP/ulaw → PCM 16kHz → WebSocket chunks"""
    def __init__(self, rtp_port: int, worker_ws: str, session_id: str):
        self.rtp_port = rtp_port
        self.worker_ws = worker_ws
        self.session_id = session_id
        self.ffmpeg = None
        self.ws = None

    async def start(self):
        # We start ffmpeg to listen on rtp_port and output PCM 16kHz
        self.ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-f", "rtp", "-i", f"rtp://127.0.0.1:{self.rtp_port}",
            "-ar", "16000", "-ac", "1", "-f", "s16le", "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self.ws = await websockets.connect(self.worker_ws)
        asyncio.create_task(self._forward_audio())
        asyncio.create_task(self._receive_audio())

    async def _forward_audio(self):
        CHUNK_SIZE = 1024
        while True:
            chunk = await self.ffmpeg.stdout.read(CHUNK_SIZE)
            if not chunk:
                break
            # Wrap audio in 0x01
            buffer = b'\x01' + chunk
            await self.ws.send(buffer)
            
    async def _receive_audio(self):
        # We receive audio from moshi-worker WS and we would send it back to Asterisk
        # For Asterisk, typically we use ExternalMedia or play it via ARI
        # For simplicity, we just log here or we could pipe it back
        async for msg in self.ws:
            if isinstance(msg, bytes):
                # audio payload
                pass
            
    async def stop(self):
        if self.ffmpeg:
            self.ffmpeg.terminate()
        if self.ws:
            await self.ws.close()

async def get_worker_ws():
    """Connect to API Gateway to get assigned GPU worker WS URL."""
    async with websockets.connect(GATEWAY_URL) as gw:
        # Wait for handshake or worker_assigned
        async for msg in gw:
            if isinstance(msg, bytes):
                continue
            data = json.loads(msg)
            if data.get("type") == "worker_assigned":
                return data["ws_url"], data["sessionId"]

async def on_stasis_start(channel_id: str, caller_id: str):
    logger.info(f"StasisStart for channel {channel_id} (Caller: {caller_id})")
    
    # 1. Answer call
    async with aiohttp.ClientSession() as session:
        await session.post(f"{ARI_URL}/channels/{channel_id}/answer", auth=aiohttp.BasicAuth(ARI_USER, ARI_PASS))

    # 2. Get AI Session
    worker_ws, session_id = await get_worker_ws()
    logger.info(f"Assigned Worker WS: {worker_ws}")

    # 3. Start RTP bridge
    global PORT_COUNTER
    rtp_port = PORT_COUNTER
    PORT_COUNTER += 2
    bridge = RTPBridge(rtp_port=rtp_port, worker_ws=worker_ws, session_id=session_id)
    ACTIVE_CALLS[channel_id] = { "session_id": session_id, "bridge": bridge }
    await bridge.start()

    # 4. Connect External Media
    async with aiohttp.ClientSession() as session:
        payload = {
            "app": ARI_APP,
            "external_host": f"127.0.0.1:{rtp_port}",
            "format": "ulaw"
        }
        await session.post(
            f"{ARI_URL}/channels/externalMedia",
            json=payload,
            auth=aiohttp.BasicAuth(ARI_USER, ARI_PASS)
        )

async def on_stasis_end(channel_id: str):
    logger.info(f"StasisEnd for channel {channel_id}")
    call = ACTIVE_CALLS.pop(channel_id, None)
    if call:
        await call["bridge"].stop()

async def ari_event_loop():
    url = f"{ARI_WS_URL}?app={ARI_APP}&api_key={ARI_USER}:{ARI_PASS}"
    while True:
        try:
            async with websockets.connect(url) as ws:
                logger.info("Connected to Asterisk ARI WebSocket")
                async for msg in ws:
                    event = json.loads(msg)
                    if event.get("type") == "StasisStart":
                        channel_id = event["channel"]["id"]
                        caller_id = event["channel"]["caller"]["number"]
                        asyncio.create_task(on_stasis_start(channel_id, caller_id))
                    elif event.get("type") == "StasisEnd":
                        channel_id = event["channel"]["id"]
                        asyncio.create_task(on_stasis_end(channel_id))
        except Exception as e:
            logger.error(f"ARI WebSocket error: {e}")
        logger.info("Reconnecting ARI WebSocket in 5 seconds...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(ari_event_loop())
