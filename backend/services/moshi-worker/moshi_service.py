"""Moshi Service — bridges Redis pub/sub to the Moshi inference engine."""

import asyncio
import json
import logging
import os

import numpy as np
import redis.asyncio as redis
from aiohttp import web
from dotenv import load_dotenv
from moshi_inference import MoshiInferenceService
from vad import EnergyVAD, VADSession
from structured_logging import setup_structured_logging, set_session_id, set_worker_id
load_dotenv()

# Setup structured JSON logging
setup_structured_logging("moshi-worker", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("MoshiService")

class MoshiService:
    """Listens on Redis for audio streams and runs Moshi inference."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.inference = MoshiInferenceService()
        self.redis_conn = None
        self.worker_id = os.getenv("WORKER_ID", "worker_01")
        self.active_sessions: set[str] = set()
        self.max_concurrent_sessions = int(os.getenv("MAX_CONCURRENT_SESSIONS", "10"))
        self.vad = EnergyVAD(
            speech_threshold_db=float(os.getenv("VAD_SPEECH_THRESHOLD_DB", "-20")),
            silence_threshold_db=float(os.getenv("VAD_SILENCE_THRESHOLD_DB", "-25")),
            min_speech_ms=int(os.getenv("VAD_MIN_SPEECH_MS", "250")),
            min_silence_ms=int(os.getenv("VAD_MIN_SILENCE_MS", "500")),
        )
        self.vad_sessions: dict[str, VADSession] = {}
        self.vad_audio_buffers: dict[str, list[np.ndarray]] = {}
        self.session_queue: asyncio.Queue[str] = asyncio.Queue()
        self.ws_clients: dict[str, web.WebSocketResponse] = {}

    async def _heartbeat(self):
        while True:
            if self.redis_conn:
                try:
                    await self.redis_conn.publish("orchestrator:worker:heartbeat", json.dumps({
                        "worker_id": self.worker_id,
                        "active_sessions": list(self.active_sessions),
                        "max_sessions": self.max_concurrent_sessions,
                    }))
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
            await asyncio.sleep(5)

    async def _health_handler(self, request: web.Request) -> web.Response:
        """GET /health — returns adapter status, GPU memory, and active sessions."""
        import torch
        engine = self.inference.engine
        adapter_status = engine.get_adapter_status()
        gpu = {}
        if torch.cuda.is_available():
            gpu["allocated_gb"] = round(torch.cuda.memory_allocated() / 1e9, 2)
            gpu["reserved_gb"]   = round(torch.cuda.memory_reserved()  / 1e9, 2)
            gpu["device"]        = torch.cuda.get_device_name(0)
        payload = {
            "status": "ok",
            "worker_id": self.worker_id,
            "active_sessions": len(self.active_sessions),
            "max_sessions": self.max_concurrent_sessions,
            "adapter": adapter_status,
            "gpu": gpu,
            "vad": self.vad.get_stats(active_sessions=len(self.vad_sessions)),
        }
        return web.json_response(payload)

    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        # max_msg_size=0 disables the 4MiB cap; receive_timeout=45s cleans up zombie connections
        ws = web.WebSocketResponse(max_msg_size=0, receive_timeout=45)
        await ws.prepare(request)
        session_id = request.query.get("session_id", "unknown")

        # Enforce max concurrent session limit
        if len(self.active_sessions) >= self.max_concurrent_sessions:
            await ws.send_str(json.dumps({
                "type": "error",
                "code": "capacity_exceeded",
                "message": f"Worker at capacity ({len(self.active_sessions)}/{self.max_concurrent_sessions})"
            }))
            await ws.close()
            logger.warning(f"Session {session_id} rejected: capacity exceeded")
            return ws

        self.active_sessions.add(session_id)
        self.ws_clients[session_id] = ws

        # Update Redis worker status
        if self.redis_conn:
            await self.redis_conn.hset(f"moshi:workers:{self.worker_id}", mapping={
                "status": "busy" if self.active_sessions else "idle",
                "sessions": len(self.active_sessions),
            })

        logger.info(f"WebSocket connection opened for session {session_id} ({len(self.active_sessions)}/{self.max_concurrent_sessions})")

        # Send session_ready handshake so the client knows Moshi is ready for audio
        await ws.send_str(json.dumps({
            "type": "session_ready",
            "session_id": session_id,
            "worker_id": self.worker_id,
            "slots_remaining": self.max_concurrent_sessions - len(self.active_sessions),
        }))

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    await self.process_audio(session_id, msg.data)
                elif msg.type == web.WSMsgType.TEXT:
                    try:
                        ctrl = json.loads(msg.data)
                        if ctrl.get("type") == "ping":
                            # Application-level ping — reply immediately so benchmark recv() succeeds
                            await ws.send_str(json.dumps({"type": "pong", "session_id": session_id}))
                            continue
                    except json.JSONDecodeError:
                        pass
                    await self.handle_control(session_id, msg.data.encode('utf-8'))
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WS error for session {session_id}: {ws.exception()}")
                elif msg.type == web.WSMsgType.CLOSE:
                    logger.info(f"WS close frame received for session {session_id}")
                    break
        except asyncio.TimeoutError:
            logger.warning(f"Session {session_id}: no data for 45s — closing stale connection")
        except Exception as e:
            logger.error(f"WS handler error for session {session_id}: {e}")
        finally:
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
            if session_id in self.ws_clients:
                del self.ws_clients[session_id]
            # Clean up VAD state
            self.vad_sessions.pop(session_id, None)
            self.vad_audio_buffers.pop(session_id, None)
            logger.info(f"WebSocket closed for session {session_id} ({len(self.active_sessions)}/{self.max_concurrent_sessions})")
            # Update Redis worker status
            if self.redis_conn:
                try:
                    await self.redis_conn.hset(f"moshi:workers:{self.worker_id}", mapping={
                        "status": "idle" if not self.active_sessions else "busy",
                        "sessions": len(self.active_sessions),
                    })
                    await self.redis_conn.publish("orchestrator:session:release", self.worker_id)
                except Exception as redis_err:
                    logger.error(f"Redis release error for session {session_id}: {redis_err}")
        return ws

    async def _start_health_server(self):
        """Start a lightweight HTTP/WS server for health checks and direct WS connection on port 8001."""
        health_port = int(os.getenv("HEALTH_PORT", "8001"))
        app = web.Application()
        app.router.add_get("/health", self._health_handler)
        app.router.add_get("/ws", self._ws_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", health_port)
        await site.start()
        self.ws_url = f"ws://127.0.0.1:{health_port}/ws"
        logger.info(f"Health endpoint running at http://0.0.0.0:{health_port}/health")
        logger.info(f"WebSocket endpoint running at {self.ws_url}")

    async def run(self):
        self.redis_conn = redis.from_url(self.redis_url, health_check_interval=30)
        # worker_id is already set in __init__ from env var

        # Start health-check and WS HTTP server
        await self._start_health_server()

        # Register GPU worker
        await self.redis_conn.hset(f"moshi:workers:{self.worker_id}", mapping={
            "status": "idle",
            "sessions": 0,
            "max_sessions": self.max_concurrent_sessions,
            "worker_id": self.worker_id,
            "ws_url": self.ws_url,
        })
        logger.info(f"Registered GPU Worker: {self.worker_id} (max={self.max_concurrent_sessions})")

        asyncio.create_task(self._heartbeat())

        pubsub = self.redis_conn.pubsub()
        await pubsub.psubscribe(
            "session:*:audio_in", 
            "session:*:text_in", 
            "session:*:control", 
            "session:start", 
            "session:update_prompt",
            f"orchestrator:session:assign:{self.worker_id}"
        )

        asyncio.create_task(self._queue_listener())

        logger.info("Moshi Service started, waiting for audio streams...")

        while True:
            try:
                async for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue

                    channel = message["channel"].decode()
                    
                    if channel == f"orchestrator:session:assign:{self.worker_id}":
                        assigned_session = message["data"].decode()
                        self.active_sessions.add(assigned_session)
                        logger.info(f"Worker {self.worker_id} assigned to session {assigned_session}")
                        continue

                    session_id = channel.split(":")[1] if ":" in channel else "unknown"

                    try:
                        if channel == "session:start":
                            # Extract session_id from data for global channels
                            msg_data = json.loads(message["data"])
                            sid = msg_data.get("sessionId")
                            if sid and sid in self.active_sessions:
                                await self.handle_session_start(message["data"])
                        elif channel == "session:update_prompt":
                            msg_data = json.loads(message["data"])
                            sid = msg_data.get("sessionId") or msg_data.get("session_id")
                            if sid and sid in self.active_sessions:
                                await self.handle_update_prompt(message["data"])
                        elif session_id != "unknown" and session_id in self.active_sessions:
                            # Session-specific channels
                            if channel.endswith(":audio_in"):
                                await self.process_audio(session_id, message["data"])
                            elif channel.endswith(":text_in"):
                                await self.process_text(session_id, message["data"])
                            elif channel.endswith(":control"):
                                await self.handle_control(session_id, message["data"])
                    except Exception as e:
                        logger.error(
                            f"Error processing {channel} for session {session_id}: {e}",
                            exc_info=True,
                        )
            except Exception as e:
                logger.error(f"Redis pubsub connection error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
                try:
                    self.redis_conn = redis.from_url(self.redis_url, health_check_interval=30)
                    pubsub = self.redis_conn.pubsub()
                    await pubsub.psubscribe(
                        "session:*:audio_in", 
                        "session:*:text_in", 
                        "session:*:control", 
                        "session:start", 
                        "session:update_prompt",
                        f"orchestrator:session:assign:{self.worker_id}"
                    )
                except Exception as reconnect_e:
                    logger.error(f"Failed to resubscribe to Redis: {reconnect_e}")

    async def _queue_listener(self):
        """Worker pool listener for text prompts via BLPOP."""
        logger.info("Started BLPOP listener on aziza:text_in:queue")
        while True:
            try:
                if not self.redis_conn:
                    await asyncio.sleep(1)
                    continue
                result = await self.redis_conn.blpop("aziza:text_in:queue", timeout=1)
                if result:
                    _, data = result
                    msg = json.loads(data)
                    session_id = msg.get("session_id", "unknown_text_session")
                    text_prompt = msg.get("text", "")
                    language = msg.get("language")
                    if text_prompt:
                        self.active_sessions.add(session_id)
                        if language:
                            state = self.inference.engine.get_session_state(session_id)
                            if state:
                                state["text_prompt"] = f"Please speak in {language}."
                        await self.process_text(session_id, text_prompt.encode('utf-8'))
            except Exception as e:
                logger.error(f"Queue listener error: {e}")
                await asyncio.sleep(1)

    async def process_audio(self, session_id: str, audio_bytes: bytes):
        """Convert bytes → numpy → run VAD → inference → publish results."""
        if len(audio_bytes) < 2:
            return
        
        # Check VRAM before processing to prevent OOM errors
        import torch
        if torch.cuda.is_available() and torch.cuda.memory_reserved() > torch.cuda.get_device_properties(0).total_memory * 0.90:
            logger.error(f"GPU memory exceeded 90% for session {session_id}, skipping inference")
            ws = (self.ws_clients or {}).get(session_id)
            if ws and not ws.closed:
                await ws.send_str(json.dumps({"type": "error", "code": "gpu_oom", "message": "GPU memory exceeded 90%"}))
            return
             
        # Strip the 0x01 (TAG_AUDIO) or 0x03 (TAG_CTRL) prefix if present.
        # Frontend and Redis pubsub both prefix binary frames with a 1-byte tag.
        tag = audio_bytes[0]
        if tag in (0x01, 0x03):
            audio_bytes = audio_bytes[1:]
        
        # Convert bytes to numpy array (16-bit PCM)
        if len(audio_bytes) % 2 != 0:
            logger.warning(f"Odd number of bytes received after tag strip: {len(audio_bytes)}")
            audio_bytes = audio_bytes[:-1]
            
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        if len(audio_np) == 0:
            return

        # Get or create VAD session
        if session_id not in self.vad_sessions:
            self.vad_sessions[session_id] = VADSession()
        self.vad_audio_buffers.setdefault(session_id, [])
        
        vad_session = self.vad_sessions[session_id]
        
        # Run VAD on audio chunk
        vad_result = self.vad.process_chunk(vad_session, audio_np)
        
        # Always buffer audio while speaking
        if vad_result["is_speech"] or vad_session.state.value in ("speaking", "trailing_silence"):
            self.vad_audio_buffers[session_id].append(audio_np)
        
        # Send VAD state update to client
        ws = (self.ws_clients or {}).get(session_id)
        if ws and not ws.closed:
            try:
                ctrl_msg = json.dumps({
                    "type": "vad_state",
                    "state": vad_result["state"],
                    "is_speech": vad_result["is_speech"],
                })
                await ws.send_bytes(b'\x03' + ctrl_msg.encode('utf-8'))
            except (ConnectionResetError, asyncio.CancelledError):
                pass
        
        # End of turn — process accumulated audio
        if vad_result["is_end_of_turn"]:
            buffer = self.vad_audio_buffers.pop(session_id, [])
            if buffer:
                # Concatenate all audio chunks
                full_audio = np.concatenate(buffer)
                logger.info(
                    f"End of turn for {session_id}: "
                    f"{len(full_audio)} samples ({len(full_audio)/24000*1000:.0f}ms)"
                )
                
                # Fetch dynamic context from PersonaPlex
                context = await self.redis_conn.get(f"persona:context:{session_id}")
                if context:
                    context_str = context.decode('utf-8')
                    state = self.inference.engine.get_session_state(session_id)
                    if state.get("text_prompt") != context_str:
                        state["text_prompt"] = context_str
                        logger.info(f"Injected persona context for {session_id}: {context_str}")
                
                # Run inference on complete utterance
                output = await self.inference.process_audio_stream(session_id, full_audio)
                
                # Publish results
                await self._publish_output(session_id, output)

    async def _publish_output(self, session_id: str, output: dict):
        """Publish inference output (audio + text) to client or Redis."""
        ws = (self.ws_clients or {}).get(session_id)
        has_ws = ws and not ws.closed
        
        # Publish generated audio
        if output.get("audio") is not None:
            generated_audio = output["audio"].cpu().numpy().tobytes()
            if has_ws:
                try:
                    await ws.send_bytes(b'\x01' + generated_audio)
                except (ConnectionResetError, asyncio.CancelledError) as e:
                    logger.warning(f"Audio send failed for {session_id}: {e} — falling back to Redis")
                    await self.redis_conn.publish(f"session:{session_id}:playback", generated_audio)
            else:
                await self.redis_conn.publish(f"session:{session_id}:playback", generated_audio)

        # Publish generated text
        text = output.get("text")
        if text:
            if isinstance(text, list):
                text = " ".join(text)
            if has_ws:
                try:
                    await ws.send_bytes(b'\x02' + text.encode('utf-8'))
                except (ConnectionResetError, asyncio.CancelledError) as e:
                    logger.warning(f"Text send failed for {session_id}: {e} — falling back to Redis")
                    await self.redis_conn.publish(f"session:{session_id}:tokens", text.encode('utf-8'))
            else:
                await self.redis_conn.publish(f"session:{session_id}:tokens", text.encode('utf-8'))

    async def process_text(self, session_id: str, text_bytes: bytes):
        """Process incoming text input (Text-to-Text / Text-to-Voice)."""
        text_str = text_bytes.decode('utf-8')
        logger.info(f"Received text input for session {session_id}: {text_str}")
        
        # Currently, Moshi is heavily audio-first, but we can push text as context
        # or have the engine yield an audio/text response based on the text prompt.
        output = await self.inference.process_text_stream(session_id, text_str)
        
        if output.get("audio") is not None:
            generated_audio = output["audio"].cpu().numpy().tobytes()
            if hasattr(self, 'ws_clients') and session_id in self.ws_clients:
                ws = self.ws_clients[session_id]
                if not ws.closed:
                    buffer = b'\x01' + generated_audio
                    await ws.send_bytes(buffer)
            else:
                await self.redis_conn.publish(f"session:{session_id}:playback", generated_audio)

        response_text = output.get("text")
        if response_text:
            if isinstance(response_text, list):
                response_text = " ".join(response_text)
            if hasattr(self, 'ws_clients') and session_id in self.ws_clients:
                ws = self.ws_clients[session_id]
                if not ws.closed:
                    buffer = b'\x02' + response_text.encode('utf-8')
                    await ws.send_bytes(buffer)
            else:
                await self.redis_conn.publish(f"session:{session_id}:tokens", response_text.encode('utf-8'))

    async def handle_control(self, session_id: str, control_data: bytes):
        """Handle control messages."""
        try:
            # Check if it's a raw string like "INTERRUPT"
            action = control_data.decode('utf-8')
            if action == "INTERRUPT" or action == "stop_audio":
                await self.inference.cancel(session_id)
                # Reset VAD state so next utterance starts fresh
                if session_id in self.vad_sessions:
                    self.vad.reset(self.vad_sessions[session_id])
                    self.vad_audio_buffers.pop(session_id, None)
                logger.info(f"Interrupted session {session_id}")
                return

            msg = json.loads(control_data)
            
            msg_type = msg.get("type")
            if msg_type == "inject_context":
                context_text = msg.get("text", "")
                await self.redis_conn.set(f"persona:context:{session_id}", context_text)
                logger.info(f"Context injected for {session_id}: {context_text}")
                return
            elif msg_type == "session_update":
                language = msg.get("language")
                old_language = state.get("language", "en") if (state := self.inference.engine.get_session_state(session_id)) else "en"
                logger.info(f"Session {session_id} changing language: {old_language} -> {language}")
                
                # Reset VAD state to avoid stale detection from previous language
                if session_id in self.vad_sessions:
                    self.vad.reset(self.vad_sessions[session_id])
                    self.vad_audio_buffers.pop(session_id, None)
                    logger.debug(f"Reset VAD state for session {session_id} after language change")
                
                context_map = {
                    "ru": "Please speak in Russian.",
                    "ru_colloquial": "Please speak in colloquial Russian.",
                    "ru_professional": "Please speak in professional Russian.",
                    "uz": "Please speak in Uzbek.",
                    "uz_latin": "Please speak in Uzbek Latin script.",
                    "uz_cyrillic": "Please speak in Uzbek Cyrillic script.",
                    "en": "Please speak in English.",
                }
                context_str = context_map.get(language, "Please speak in English.")

                # Update session language and context
                state = self.inference.engine.get_session_state(session_id)
                if state:
                    state["text_prompt"] = context_str
                    state["language"] = language
                
                # Also save to redis so it persists for this session if reloaded
                await self.redis_conn.set(f"persona:context:{session_id}", context_str)
                
                # Notify client of language change confirmation
                ws = self.ws_clients.get(session_id)
                if ws and not ws.closed:
                    try:
                        await ws.send_bytes(b'\x03' + json.dumps({
                            "type": "language_changed",
                            "language": language,
                            "previous_language": old_language,
                        }).encode('utf-8'))
                    except (ConnectionResetError, asyncio.CancelledError):
                        pass
                return
                
            action = msg.get("action")
            if action == "stop_audio":
                await self.inference.cancel(session_id)
                logger.info(f"Stopped audio for session {session_id}")
                if session_id in self.active_sessions:
                    self.active_sessions.remove(session_id)
                    await self.redis_conn.publish("orchestrator:session:release", self.worker_id)
        except Exception as e:
            logger.error(f"Error handling control for {session_id}: {e}")

    async def handle_session_start(self, data: bytes):
        """Initialize session with specific prompts."""
        try:
            msg = json.loads(data)
            session_id = msg.get("sessionId")
            text_prompt = msg.get("text_prompt")
            voice_prompt = msg.get("voice_prompt")
            
            logger.info(f"Starting session {session_id} with custom prompts")
            self.inference.engine.initialize_session(session_id, text_prompt, voice_prompt)
        except Exception as e:
            logger.error(f"Error handling session:start: {e}")

    async def handle_update_prompt(self, data: bytes):
        """Dynamic prompt injection (Phase 6/7)."""
        try:
            msg = json.loads(data)
            session_id = msg.get("sessionId") or msg.get("session_id")
            prompt = msg.get("prompt")
            logger.info(f"Updating prompt for {session_id}")
            self.inference.engine.initialize_session(session_id, text_prompt=prompt)
        except Exception as e:
            logger.error(f"Error updating prompt for {session_id}: {e}")

if __name__ == "__main__":
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    service = MoshiService(redis_url=redis_url)
    asyncio.run(service.run())
