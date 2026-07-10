"""Streaming Runtime — session lifecycle, VAD, interruptions, Redis coordination."""

import asyncio
import redis.asyncio as redis
import json
import logging
import os
from state_machine import SessionStateMachine, SessionState
from vad_controller import VADController

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StreamingRuntime")

# 30ms of 16kHz 16-bit mono PCM = 480 samples × 2 bytes = 960 bytes
FRAME_SIZE = 960


class StreamingRuntime:
    """Manages per-session streaming state, VAD detection, and interruptions."""

    def __init__(self, redis_url: str = None):
        if redis_url is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_url = redis_url
        self.sessions: dict = {}
        self.redis_conn = None

    async def run(self):
        self.redis_conn = redis.from_url(self.redis_url)
        pubsub = self.redis_conn.pubsub()
        await pubsub.psubscribe("session:*:audio_in", "session:*:vad")

        logger.info("Streaming Runtime started, listening to sessions...")

        async for message in pubsub.listen():
            logger.debug(f"Received Redis message: {message['type']} on {message.get('channel')}")
            if message["type"] != "pmessage":
                continue

            channel = message["channel"].decode()
            session_id = channel.split(":")[1]
            data = message["data"]
            
            logger.info(f"Processing {channel} for session {session_id} ({len(data)} bytes)")

            try:
                if channel.endswith(":audio_in"):
                    await self.handle_audio(session_id, data)
                elif channel.endswith(":vad"):
                    await self.handle_vad(session_id, data)
            except Exception as e:
                logger.error(f"Error handling message on {channel}: {e}", exc_info=True)

    async def get_session(self, session_id: str) -> dict:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "sm": SessionStateMachine(session_id),
                "vad": VADController(),
                "current_task": None,
                "audio_buffer": bytearray(),
            }
        return self.sessions[session_id]

    async def handle_audio(self, session_id: str, audio_data: bytes):
        """Buffer incoming audio, slice into VAD-safe frames, and route."""
        session = await self.get_session(session_id)
        sm = session["sm"]
        vad = session["vad"]
        buf = session["audio_buffer"]

        buf.extend(audio_data)

        # Process complete frames
        while len(buf) >= FRAME_SIZE:
            frame = bytes(buf[:FRAME_SIZE])
            del buf[:FRAME_SIZE]

            if vad.is_speech(frame):
                if sm.is_active():
                    logger.info(f"Interruption detected in session {session_id}!")
                    await self.interrupt_session(session_id)
                elif sm.state == SessionState.IDLE:
                    sm.transition_to(SessionState.LISTENING)

                # Forward audio to Moshi for processing
                await self.redis_conn.publish(
                    f"session:{session_id}:audio", frame
                )
            else:
                if sm.state == SessionState.LISTENING:
                    # End of speech — trigger inference
                    sm.transition_to(SessionState.THINKING)
                    session["current_task"] = asyncio.create_task(
                        self.process_thinking(session_id)
                    )

    async def handle_vad(self, session_id: str, data: bytes):
        """Handle external VAD signals from Gateway."""
        try:
            payload = json.loads(data)
            if payload.get("speech") is False:
                session = await self.get_session(session_id)
                sm = session["sm"]
                if sm.state == SessionState.LISTENING:
                    sm.transition_to(SessionState.THINKING)
                    session["current_task"] = asyncio.create_task(
                        self.process_thinking(session_id)
                    )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Bad VAD payload for {session_id}: {e}")

    async def interrupt_session(self, session_id: str):
        session = await self.get_session(session_id)
        sm = session["sm"]

        sm.transition_to(SessionState.INTERRUPTING)

        if session["current_task"]:
            session["current_task"].cancel()
            try:
                await session["current_task"]
            except asyncio.CancelledError:
                logger.info(f"Task for session {session_id} cancelled.")

        # Flush buffers and notify Moshi
        await self.redis_conn.publish(
            f"session:{session_id}:control",
            json.dumps({"action": "stop_audio"}),
        )

        sm.transition_to(SessionState.RECOVERING)
        await asyncio.sleep(0.1)  # Grace period
        sm.transition_to(SessionState.LISTENING)

    async def process_thinking(self, session_id: str):
        session = await self.get_session(session_id)
        sm = session["sm"]

        try:
            sm.transition_to(SessionState.GENERATING)

            # In real flow, Moshi handles generation via Redis pub/sub.
            # Here we just wait for playback data from the moshi service.
            sm.transition_to(SessionState.STREAMING)

            # Subscribe to playback and wait for completion
            playback_sub = self.redis_conn.pubsub()
            await playback_sub.subscribe(f"session:{session_id}:playback")

            timeout = 10.0
            start = asyncio.get_event_loop().time()
            async for msg in playback_sub.listen():
                if msg["type"] == "message":
                    # Playback chunk received — session stays in STREAMING
                    pass
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > timeout:
                    break

            await playback_sub.unsubscribe()
            sm.transition_to(SessionState.IDLE)

        except asyncio.CancelledError:
            logger.info(
                f"Thinking process for {session_id} cancelled during generation."
            )
            raise

    def cleanup_session(self, session_id: str):
        """Remove session state entirely."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if session["current_task"]:
                session["current_task"].cancel()
            session["vad"].reset()
            del self.sessions[session_id]
            logger.info(f"Cleaned up session {session_id}")


if __name__ == "__main__":
    runtime = StreamingRuntime()
    asyncio.run(runtime.run())
