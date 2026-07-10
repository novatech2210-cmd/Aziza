import asyncio
import websockets
from typing import Dict

ACTIVE_CALLS: Dict[str, dict] = {}

class RTPBridge:
    """FFmpeg pipeline: RTP/ulaw → PCM 16kHz → WebSocket chunks"""
    
    def __init__(self, rtp_port: int, worker_ws: str, session_id: str):
        self.rtp_port = rtp_port
        self.worker_ws = worker_ws
        self.session_id = session_id
        self.ffmpeg = None
        self.ws = None

    async def start(self):
        self.ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-f", "rtp", "-i", f"rtp://127.0.0.1:{self.rtp_port}",
            "-ar", "16000", "-ac", "1", "-f", "s16le", "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self.ws = await websockets.connect(self.worker_ws)
        asyncio.create_task(self._forward_audio())

    async def _forward_audio(self):
        CHUNK_SIZE = 1024  # ~32ms at 16kHz
        while True:
            chunk = await self.ffmpeg.stdout.read(CHUNK_SIZE)
            if not chunk:
                break
            await self.ws.send(chunk)
            
    async def stop(self):
        if self.ffmpeg:
            self.ffmpeg.terminate()
        if self.ws:
            await self.ws.close()

# Mocking external API interfaces for completeness
class API_Gateway:
    async def create_session(self, caller_id):
        return {"session_id": f"sess_{caller_id}", "worker_ws_url": "ws://localhost:3000/ws"}
        
    async def release_session(self, session_id):
        pass

api_gateway = API_Gateway()

class AsteriskChannels:
    async def answer(self, channelId):
        pass
    async def externalMedia(self, channelId, app, external_host, format):
        pass

class Asterisk:
    def __init__(self):
        self.channels = AsteriskChannels()

asterisk = Asterisk()

def allocate_rtp_port():
    return 10000

async def on_stasis_start(channel_id: str, caller_id: str):
    # 1. Create AI session via API Gateway
    session = await api_gateway.create_session(caller_id=caller_id)
    worker_ws = session["worker_ws_url"]

    # 2. Start RTP bridge
    rtp_port = allocate_rtp_port()
    bridge = RTPBridge(
        rtp_port=rtp_port,
        worker_ws=worker_ws,
        session_id=session["session_id"]
    )
    ACTIVE_CALLS[channel_id] = { "session": session, "bridge": bridge }
    await bridge.start()

    # 3. Answer call and connect RTP
    await asterisk.channels.answer(channelId=channel_id)
    await asterisk.channels.externalMedia(
        channelId=channel_id,
        app="aziza",
        external_host=f"127.0.0.1:{rtp_port}",
        format="ulaw"
    )

async def on_stasis_end(channel_id: str):
    call = ACTIVE_CALLS.pop(channel_id, None)
    if call:
        await call["bridge"].stop()
        await api_gateway.release_session(call["session"]["session_id"])
