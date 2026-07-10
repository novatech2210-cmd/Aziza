#!/usr/bin/env python3
"""
Aziza Mock Gateway Server
Simulates the API gateway for local benchmark testing.
Speaks the same binary protocol as voice.gateway.ts:
  - 0x01 prefix = audio frame
  - 0x02 prefix = text token

Runs on ws://127.0.0.1:8080/api/chat
"""

import asyncio
import json
import random
import time
import struct
import math
import logging
import signal
import sys
from typing import Dict, Optional

try:
    import websockets
    from websockets.server import serve
    from websockets.legacy.server import WebSocketServerProtocol
except ImportError:
    print("ERROR: websockets not installed. Run: pip install websockets")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="[MockGateway] %(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# Simulated latency range (ms) - mirrors realistic worker response times
BASE_LATENCY_MS = 80
JITTER_MS = 40

# Audio streaming config
AUDIO_SAMPLE_RATE = 24000  # Moshi output sample rate
AUDIO_CHUNK_MS = 80        # chunk size in ms
AUDIO_CHUNKS_PER_RESPONSE = 5  # number of chunks to send per response

SESSIONS: Dict[str, dict] = {}


def generate_fake_audio_chunk(duration_ms: int = AUDIO_CHUNK_MS) -> bytes:
    """Generate a synthetic PCM audio chunk (sine wave, matches Moshi format)."""
    num_samples = int(AUDIO_SAMPLE_RATE * duration_ms / 1000)
    samples = []
    for i in range(num_samples):
        # 440 Hz sine wave at 30% amplitude
        val = int(16000 * 0.3 * math.sin(2 * math.pi * 440 * i / AUDIO_SAMPLE_RATE))
        val = max(-32768, min(32767, val))
        samples.append(struct.pack('<h', val))
    return b''.join(samples)


async def handle_ttft_session(websocket, session_id: str, language: str = "ru"):
    """
    Handle TTFT benchmark requests: send worker_assigned + first_token quickly.
    No audio expected — just measures time-to-first-token.
    """
    SESSIONS[session_id] = {"start": time.time(), "language": language, "type": "ttft"}
    try:
        # 1. worker_assigned
        await websocket.send(json.dumps({
            "type": "worker_assigned",
            "session_id": session_id,
            "worker_id": "mock-worker-01",
            "status": "ready"
        }))

        # 2. Simulate adapter + inference latency then first token
        latency_s = (BASE_LATENCY_MS + random.uniform(0, JITTER_MS)) / 1000
        await asyncio.sleep(latency_s)

        # 3. adapter_ingest signal
        await websocket.send(json.dumps({"type": "adapter_ingest", "session_id": session_id}))
        await asyncio.sleep(0.005)

        # 4. moshi_inference_start signal
        await websocket.send(json.dumps({"type": "moshi_inference_start", "session_id": session_id}))
        await asyncio.sleep(0.005)

        # 5. first_token — this is what the TTFT benchmark waits for
        sample = {"ru": "Прив", "uz": "Sal", "en": "Hel"}.get(language, "Прив")
        await websocket.send(json.dumps({
            "type": "first_token",
            "token": sample,
            "session_id": session_id
        }))

        # Stream remaining tokens
        tokens = {"ru": ["ет, ", "я ", "Азиза."], "uz": ["om, ", "men ", "Aziza."], "en": ["lo, ", "I'm ", "Aziza."]}
        for tok in tokens.get(language, tokens["ru"]):
            await websocket.send(json.dumps({"type": "token", "token": tok, "session_id": session_id}))
            await asyncio.sleep(0.015)

        await websocket.send(json.dumps({"type": "done", "session_id": session_id}))

        # Wait for end_session
        try:
            msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
    except Exception as e:
        log.debug(f"[{session_id[:8]}] TTFT session ended: {e}")
    finally:
        SESSIONS.pop(session_id, None)


async def handle_stability_session(websocket, session_id: str, language: str = "ru"):
    """
    Handle stability test: keep connection alive, respond to pings, handle persona switches.
    Runs until client sends end_session or disconnects.
    """
    SESSIONS[session_id] = {"start": time.time(), "language": language, "type": "stability"}
    try:
        await websocket.send(json.dumps({
            "type": "worker_assigned",
            "session_id": session_id,
            "worker_id": "mock-worker-01",
            "status": "ready"
        }))
        log.info(f"[{session_id[:8]}] Stability session started")

        # Main stability loop — respond to pings, handle switches
        while True:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=15.0)
            except asyncio.TimeoutError:
                log.debug(f"[{session_id[:8]}] Stability timeout, closing")
                break

            if isinstance(msg, bytes):
                continue  # ignore binary

            try:
                data = json.loads(msg)
                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong", "session_id": session_id}))

                elif msg_type == "switch_persona":
                    new_persona = data.get("persona", "aziza_ru")
                    await websocket.send(json.dumps({
                        "type": "persona_switched",
                        "session_id": session_id,
                        "persona": new_persona
                    }))
                    log.info(f"[{session_id[:8]}] Persona switched to {new_persona}")

                elif msg_type in ("end_session", "disconnect"):
                    log.info(f"[{session_id[:8]}] Stability session ended by client")
                    break

            except json.JSONDecodeError:
                pass
    except Exception as e:
        log.debug(f"[{session_id[:8]}] Stability session ended: {e}")
    finally:
        SESSIONS.pop(session_id, None)
        log.info(f"[{session_id[:8]}] Stability session cleaned up")


async def handle_voice_session(websocket, session_id: str, language: str = "ru"):
    """
    Handle a single voice session.
    Waits for audio chunks from client, then streams back audio response.
    """
    SESSIONS[session_id] = {
        "start": time.time(),
        "language": language,
        "audio_received": 0,
        "tokens_sent": 0,
    }

    try:
        # Step 1: Acknowledge session start → send worker_assigned
        ack = {
            "type": "worker_assigned",
            "session_id": session_id,
            "worker_id": "mock-worker-01",
            "status": "ready"
        }
        await websocket.send(json.dumps(ack))
        log.info(f"[{session_id[:8]}] worker_assigned sent")

        # Step 2: Wait for audio from client
        audio_bytes_received = 0
        while True:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=15.0)
            except asyncio.TimeoutError:
                log.warning(f"[{session_id[:8]}] Timeout waiting for audio")
                break

            if isinstance(msg, bytes):
                audio_bytes_received += len(msg)
                SESSIONS[session_id]["audio_received"] += len(msg)
            elif isinstance(msg, str):
                try:
                    data = json.loads(msg)
                    msg_type = data.get("type", "")

                    if msg_type == "audio_end":
                        log.info(f"[{session_id[:8]}] audio_end received ({audio_bytes_received} bytes). Processing...")
                        break

                    elif msg_type == "ping":
                        # Stability test keep-alive — respond immediately
                        await websocket.send(json.dumps({
                            "type": "pong",
                            "session_id": session_id
                        }))
                        continue

                    elif msg_type == "text_request":
                        # Simulate processing latency
                        latency_s = (BASE_LATENCY_MS + random.uniform(0, JITTER_MS)) / 1000
                        await asyncio.sleep(latency_s)
                        
                        # Send text_response JSON
                        resp = {
                            "type": "text_response",
                            "session_id": session_id,
                            "text": "Привет! Я Азиза."
                        }
                        await websocket.send(json.dumps(resp))
                        log.info(f"[{session_id[:8]}] text_response sent")
                        continue

                    elif msg_type in ("end_session", "disconnect"):
                        log.info(f"[{session_id[:8]}] Session ended by client")
                        return

                except json.JSONDecodeError:
                    pass

        if audio_bytes_received == 0:
            log.warning(f"[{session_id[:8]}] No audio received, skipping response")
            return

        # Step 3: Simulate processing latency
        latency_s = (BASE_LATENCY_MS + random.uniform(0, JITTER_MS)) / 1000
        await asyncio.sleep(latency_s)

        # Step 4: Stream audio response back (binary: 0x01 prefix = audio)
        log.info(f"[{session_id[:8]}] Streaming audio response...")
        audio_chunk = generate_fake_audio_chunk(AUDIO_CHUNK_MS)

        for chunk_i in range(AUDIO_CHUNKS_PER_RESPONSE):
            # Binary frame: 0x01 + raw audio PCM
            frame = bytes([0x01]) + audio_chunk
            await websocket.send(frame)
            SESSIONS[session_id]["tokens_sent"] += 1
            await asyncio.sleep(AUDIO_CHUNK_MS / 1000)

        # Step 5: Send a text token (binary: 0x02 prefix = token)
        token_frame = bytes([0x02]) + json.dumps({
            "text": "Привет, я Азиза!",
            "session_id": session_id,
            "is_final": True
        }).encode()
        await websocket.send(token_frame)

        # Step 6: Send JSON done signal
        done_msg = {
            "type": "playback_done",
            "session_id": session_id
        }
        await websocket.send(json.dumps(done_msg))
        log.info(f"[{session_id[:8]}] Response complete")

    except websockets.exceptions.ConnectionClosedError:
        log.info(f"[{session_id[:8]}] Client disconnected")
    except Exception as e:
        log.error(f"[{session_id[:8]}] Error: {e}")
        try:
            err = {"type": "error", "message": str(e), "session_id": session_id}
            await websocket.send(json.dumps(err))
        except Exception:
            pass
    finally:
        SESSIONS.pop(session_id, None)


async def handle_chat_message(websocket, text_msg: dict) -> Optional[str]:
    """Handle text→text chat messages (for E2E and TTFT benchmarks)."""
    prompt = text_msg.get("message", text_msg.get("content", ""))
    language = text_msg.get("language", "ru")

    # Simulate TTFT latency (first token)
    first_token_delay = (BASE_LATENCY_MS + random.uniform(0, JITTER_MS)) / 1000
    await asyncio.sleep(first_token_delay)

    # Stream fake response tokens
    sample_responses = {
        "ru": ["Привет! ", "Я ", "Азиза. ", "Как ", "дела?"],
        "uz": ["Salom! ", "Men ", "Aziza. ", "Qanday ", "yashaysiz?"],
        "en": ["Hello! ", "I'm ", "Aziza. ", "How ", "are you?"],
    }
    tokens = sample_responses.get(language, sample_responses["ru"])

    session_id = text_msg.get("session_id", "unknown")
    for token in tokens:
        msg = {
            "type": "token",
            "token": token,
            "session_id": session_id
        }
        await websocket.send(json.dumps(msg))
        await asyncio.sleep(0.01)  # inter-token delay

    # Final done
    await websocket.send(json.dumps({
        "type": "done",
        "session_id": session_id,
        "full_text": "".join(tokens)
    }))


async def connection_handler(websocket):
    """Main handler dispatching to voice or text pipelines."""
    remote = websocket.remote_address
    path = getattr(websocket, 'path', '/api/chat')
    log.info(f"Connection from {remote} on {path}")

    try:
        # Wait for initial message to determine session type
        try:
            first_msg = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        except asyncio.TimeoutError:
            log.warning(f"No initial message from {remote}")
            return

        if isinstance(first_msg, bytes):
            # Raw binary audio started immediately — treat as voice session
            session_id = f"bin-{time.time():.0f}"
            await handle_voice_session(websocket, session_id)
            return

        # Parse JSON message
        try:
            data = json.loads(first_msg)
        except json.JSONDecodeError:
            log.warning(f"Non-JSON, non-binary first message from {remote}")
            return

        msg_type = data.get("type", "")
        session_id = data.get("session_id", str(time.time()))
        language = data.get("language", "ru")

        if msg_type == "start_session":
            # Detect benchmark mode from flags
            if data.get("measure_ttft"):
                await handle_ttft_session(websocket, session_id, language)
            elif data.get("stability") or data.get("persona"):
                # Stability test opens a long-lived session with persona switches
                await handle_stability_session(websocket, session_id, language)
            else:
                # Regular voice round-trip
                await handle_voice_session(websocket, session_id, language)

        elif msg_type in ("chat", "message", "text"):
            # Text-to-text or TTFT benchmark
            await handle_chat_message(websocket, data)

            # Keep connection open for more messages
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    if isinstance(msg, str):
                        try:
                            next_data = json.loads(msg)
                            if next_data.get("type") in ("end_session", "disconnect"):
                                break
                            elif next_data.get("type") == "ping":
                                await websocket.send(json.dumps({"type": "pong", "session_id": next_data.get("session_id", "unknown")}))
                            else:
                                await handle_chat_message(websocket, next_data)
                        except json.JSONDecodeError:
                            pass
                except asyncio.TimeoutError:
                    break
        else:
            # Unknown type — acknowledge and try to handle as voice
            ack = {"type": "acknowledged", "session_id": session_id}
            await websocket.send(json.dumps(ack))
            await handle_voice_session(websocket, session_id, language)

    except websockets.exceptions.ConnectionClosedOK:
        log.info(f"Client {remote} closed connection cleanly")
    except websockets.exceptions.ConnectionClosedError as e:
        log.warning(f"Client {remote} closed unexpectedly: {e}")
    except Exception as e:
        log.error(f"Unhandled error for {remote}: {e}", exc_info=True)


async def health_endpoint(host: str = "127.0.0.1", port: int = 8081):
    """Simple HTTP health check endpoint (non-blocking)."""
    import http.server
    import threading

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/health", "/"):
                body = json.dumps({
                    "status": "ok",
                    "service": "aziza-mock-gateway",
                    "active_sessions": len(SESSIONS)
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress HTTP access logs

    server = http.server.HTTPServer((host, port), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info(f"Health endpoint: http://{host}:{port}/health")


async def main():
    host = "127.0.0.1"
    ws_port = 8080
    health_port = 8081

    log.info(f"Starting Aziza Mock Gateway on ws://{host}:{ws_port}")
    log.info(f"Binary protocol: 0x01=audio, 0x02=text-token")
    log.info(f"Simulated latency: {BASE_LATENCY_MS}±{JITTER_MS}ms")

    # Start health endpoint
    await health_endpoint(host, health_port)

    # Handle graceful shutdown
    stop = asyncio.get_event_loop().create_future()

    def handle_signal(*args):
        log.info("Shutting down...")
        stop.set_result(None)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    async with serve(
        connection_handler,
        host,
        ws_port,
        ping_interval=30,
        ping_timeout=10,
        max_size=10 * 1024 * 1024,  # 10MB max message
    ) as server:
        log.info(f"✓ Mock gateway ready. Press Ctrl+C to stop.")
        await stop

    log.info("Mock gateway stopped.")


if __name__ == "__main__":
    asyncio.run(main())
