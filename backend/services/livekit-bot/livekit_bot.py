"""
LiveKit Bot Service — bridges LiveKit audio rooms with the AZIZA Moshi worker pipeline.

Architecture:
  LiveKit Room (user audio) → LiveKit Bot → Moshi Worker (WebSocket) → Audio Response → LiveKit Room

This service acts as a LiveKit participant that:
  1. Subscribes to user audio tracks
  2. Forwards raw PCM audio to the existing Moshi worker via WebSocket
  3. Receives synthesized audio from Moshi worker
  4. Publishes audio back to the LiveKit room for playback

No changes to existing AZIZA backend (Gateway, Moshi, vLLM, PersonaPlex) are required.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Optional

import numpy as np
import redis.asyncio as redis
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, AgentServer, WorkerOptions
from livekit.agents.cli._legacy import _build_cli

load_dotenv()

logger = logging.getLogger("LiveKitBot")
logging.basicConfig(level=logging.INFO)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MOSHI_WS_URL = os.getenv("MOSHI_WS_URL", "http://localhost:8001/ws")


async def entrypoint(ctx: JobContext):
    """Main entrypoint for the LiveKit bot worker."""
    room = ctx.room
    session_id = str(uuid.uuid4())
    logger.info(f"[{session_id}] LiveKit bot started in room {room.name}")

    redis_client = redis.Redis.from_url(REDIS_URL)
    moshi_ws: Optional[rtc.WebSocket] = None
    is_speaking = False

    async def connect_moshi():
        nonlocal moshi_ws
        if not session_id:
            return

        ws_url = f"{MOSHI_WS_URL}?session_id={session_id}"
        logger.info(f"[{session_id}] Connecting to Moshi worker at {ws_url}")

        try:
            moshi_ws = await rtc.WebSocket.connect(ws_url)
            logger.info(f"[{session_id}] Connected to Moshi worker")
            asyncio.create_task(moshi_listener())
        except Exception as e:
            logger.error(f"[{session_id}] Failed to connect to Moshi worker: {e}")
            moshi_ws = None

    async def moshi_listener():
        nonlocal moshi_ws, is_speaking
        if not moshi_ws:
            return

        try:
            async for message in moshi_ws:
                if isinstance(message, bytes):
                    view = message
                    if len(view) < 1:
                        continue
                    tag = view[0]
                    payload = view[1:]

                    if tag == 0x01:  # Audio response
                        await play_audio(payload)
                    elif tag == 0x02:  # Text response
                        text = payload.decode("utf-8", errors="replace")
                        logger.info(f"[{session_id}] Text: {text[:100]}")
                    elif tag == 0x03:  # Control message
                        try:
                            ctrl = json.loads(payload.decode("utf-8"))
                            if ctrl.get("type") == "error":
                                logger.error(f"[{session_id}] Moshi error: {ctrl.get('message')}")
                        except Exception:
                            pass
                else:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "error":
                            logger.error(f"[{session_id}] Moshi error: {data.get('message')}")
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"[{session_id}] Moshi listener error: {e}")

    async def play_audio(pcm_bytes: bytes):
        nonlocal is_speaking
        try:
            audio_np = np.frombuffer(pcm_bytes, dtype=np.float32)
            if audio_np.size == 0:
                return

            frame = rtc.AudioFrame(
                data=audio_np.tobytes(),
                sample_rate=24000,
                num_channels=1,
                samples_per_channel=len(audio_np),
            )

            logger.debug(f"[{session_id}] Playing {len(pcm_bytes)} bytes of audio")
            is_speaking = True

            duration_ms = (len(audio_np) / 24000) * 1000
            await asyncio.sleep(duration_ms / 1000)
            is_speaking = False

        except Exception as e:
            logger.error(f"[{session_id}] Error playing audio: {e}")

    def convert_audio_frame(frame: rtc.AudioFrame) -> Optional[bytes]:
        """Convert LiveKit AudioFrame (48kHz stereo float32) to 24kHz mono int16 PCM."""
        try:
            samples = np.frombuffer(frame.data, dtype=np.float32)

            if frame.num_channels == 2:
                samples = samples.reshape(-1, 2)
                samples = samples.mean(axis=1)

            orig_sr = frame.sample_rate
            target_sr = 24000
            if orig_sr != target_sr:
                ratio = target_sr / orig_sr
                samples = np.interp(
                    np.arange(0, len(samples), ratio),
                    np.arange(len(samples)),
                    samples
                )

            pcm_int16 = (samples * 32767).astype(np.int16)
            return pcm_int16.tobytes()

        except Exception as e:
            logger.error(f"[{session_id}] Audio conversion error: {e}")
            return None

    async def handle_audio_track(track: rtc.Track):
        stream = rtc.AudioStream(track)
        logger.info(f"[{session_id}] Starting audio stream processing")

        async for audio_frame in stream:
            if not moshi_ws or moshi_ws.state != rtc.WebSocketState.CONNECTED:
                await connect_moshi()
                if not moshi_ws:
                    continue

            pcm_data = convert_audio_frame(audio_frame)
            if pcm_data is None:
                continue

            packet = bytes([0x01]) + pcm_data

            try:
                await moshi_ws.send(packet)
            except Exception as e:
                logger.error(f"[{session_id}] Error sending audio to Moshi: {e}")
                await connect_moshi()

        logger.info(f"[{session_id}] Audio stream ended")

    # Subscribe to remote audio tracks
    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"[{session_id}] Subscribed to audio from {participant.identity}")
            asyncio.create_task(handle_audio_track(track))

    # Connect to Moshi on start
    await connect_moshi()

    # Keep the session alive until room disconnects
    session = getattr(ctx, 'primary_session', None)
    if session is not None:
        await session.aclose()
    else:
        await asyncio.Event().wait()


def run_worker():
    """Entry point for the LiveKit bot worker."""
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        ws_url=os.getenv("LIVEKIT_URL", "ws://localhost:7880"),
        api_key=os.getenv("LIVEKIT_API_KEY", "devkey"),
        api_secret=os.getenv("LIVEKIT_API_SECRET", "devsecret"),
    )

    server = AgentServer.from_server_options(worker_options)
    cli_app = _build_cli(server)
    cli_app(["start"])


if __name__ == "__main__":
    run_worker()
