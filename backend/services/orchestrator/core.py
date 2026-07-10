import asyncio
import httpx
import json
import os
import structlog
import redis.asyncio as redis
from session_manager import SessionManager
from state_machine import SessionState

logger = structlog.get_logger()

# vLLM endpoints by language
VLLM_ENDPOINTS = {
    "en": {"host": "127.0.0.1", "port": 8002, "model": "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"},
    "ru": {"host": "127.0.0.1", "port": 8002, "model": "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"},
    "uz": {"host": "127.0.0.1", "port": 8003, "model": "alloma"},
}

# System prompts by language
SYSTEM_PROMPTS = {
    "en": "You are Aziza — a warm, intelligent, and attentive AI assistant. Speak naturally and conversationally. Keep responses concise. RESPOND ONLY IN ENGLISH.",
    "ru": "Ты Азиза — тёплый, умный и внимательный AI-ассистент. Говори естественно по-русски, как живой человек. Избегай формальных оборотов. Отвечай кратко и по делу. ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.",
    "uz": "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz. O'zbek tilida tabiiy va jonli gapiring. Qisqa va aniq javob bering. FAQAT O'ZBEK TILIDA JAVOB BERING.",
}


class AIOrchestrator:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis = None
        self.session_manager = None
        self.personaplex_url = os.getenv("PERSONA_PLEX_URL", "http://localhost:8000")
        self.http_client = httpx.AsyncClient(timeout=12.0)
        
        # Worker registry: { "worker_id": {"status": "idle", "last_heartbeat": time, "session_id": None, "last_session_end": 0} }
        self.worker_registry = {}
        
        # Background tasks
        self.pubsub_task = None
        self.heartbeat_task = None

    async def startup(self):
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        self.pubsub_redis = redis.from_url(self.redis_url, decode_responses=False)
        self.session_manager = SessionManager(self.redis)
        self.pubsub_task = asyncio.create_task(self._listen_to_redis_events())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        logger.info("AI Orchestrator started", personaplex_url=self.personaplex_url)

    async def shutdown(self):
        logger.info("Shutting down AI Orchestrator...")
        if self.pubsub_task:
            self.pubsub_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        if getattr(self, 'pubsub_redis', None):
            await self.pubsub_redis.close()
        if getattr(self, 'redis', None):
            await self.redis.close()
        await self.http_client.aclose()
        logger.info("AI Orchestrator shutdown complete.")

    async def _heartbeat_monitor(self):
        while True:
            await asyncio.sleep(5)
            now = asyncio.get_event_loop().time()
            for worker_id, worker in list(self.worker_registry.items()):
                if now - worker["last_heartbeat"] > 15:
                    logger.warning("Worker heartbeat timeout. Removing from registry.", worker_id=worker_id)
                    session_id = worker.get("session_id")
                    del self.worker_registry[worker_id]
                    if session_id:
                        logger.info("Attempting failover for session", session_id=session_id)
                        await self._route_session(session_id)

    async def _listen_to_redis_events(self):
        pubsub = self.pubsub_redis.pubsub()
        await pubsub.psubscribe("gateway:*", "session:*:audio", "session:*:vad", "orchestrator:worker:heartbeat", "orchestrator:session:release")
        
        last_audio_time = {}

        async for message in pubsub.listen():
            if message["type"] != b"pmessage":
                continue
                
            channel = message["channel"].decode('utf-8')
            
            if channel == "gateway:connection":
                await self._handle_connection(message["data"].decode('utf-8'))
            elif channel == "orchestrator:worker:heartbeat":
                self._handle_heartbeat(message["data"].decode('utf-8'))
            elif channel == "orchestrator:session:release":
                self._handle_release(message["data"].decode('utf-8'))
            elif channel.endswith(":audio"):
                session_id = channel.split(":")[1]
                last_audio_time[session_id] = asyncio.get_event_loop().time()
                # Start a turn timer if not already running
                asyncio.create_task(self._check_for_turn_end(session_id, last_audio_time))
            elif channel.endswith(":vad"):
                session_id = channel.split(":")[1]
                if message["data"] == b"1":
                    await self.trigger_interrupt(session_id)

    def _handle_heartbeat(self, data: str):
        try:
            payload = json.loads(data)
            wid = payload.get("worker_id")
            if wid:
                if wid not in self.worker_registry:
                    logger.info("New worker registered", worker_id=wid)
                    self.worker_registry[wid] = {"status": "idle", "last_heartbeat": asyncio.get_event_loop().time(), "session_id": None, "last_session_end": 0}
                else:
                    self.worker_registry[wid]["last_heartbeat"] = asyncio.get_event_loop().time()
        except json.JSONDecodeError:
            pass

    def _handle_release(self, data: str):
        wid = data
        if wid in self.worker_registry:
            logger.info("Worker released session", worker_id=wid)
            self.worker_registry[wid]["status"] = "idle"
            self.worker_registry[wid]["session_id"] = None
            self.worker_registry[wid]["last_session_end"] = asyncio.get_event_loop().time()

    async def _check_for_turn_end(self, session_id, last_audio_time):
        await asyncio.sleep(1.0) # Wait for silence
        if asyncio.get_event_loop().time() - last_audio_time.get(session_id, 0) >= 1.0:
            await self.process_conversation_turn(session_id)

    async def _route_session(self, session_id: str):
        idle_workers = [
            (wid, w) for wid, w in self.worker_registry.items()
            if w["status"] == "idle"
        ]
        if not idle_workers:
            logger.warning("No idle workers available. Session queued.")
            await self.redis.publish(f"session:{session_id}:events", json.dumps({"type": "queued", "message": "Waiting for available worker"}))
            return
        
        worker_id, worker = min(idle_workers, key=lambda x: x[1].get("last_session_end", 0))
        
        worker["status"] = "busy"
        worker["session_id"] = session_id
        await self.redis.publish(f"orchestrator:session:assign:{worker_id}", session_id)
        logger.info("Assigned session to worker", session_id=session_id, worker_id=worker_id)
        await self.redis.publish(f"session:{session_id}:events", json.dumps({"type": "worker_assigned", "worker_id": worker_id}))

    async def _handle_connection(self, data):
        try:
            payload = json.loads(data)
            session_id = payload.get("sessionId")
            params = payload.get("params", {})
            await self._route_session(session_id)
            await asyncio.sleep(0.5)
            await self.session_manager.ensure_session(session_id, params=params)
        except Exception as e:
            logger.error("Error handling gateway connection", error=str(e))

    async def process_conversation_turn(self, session_id: str, text_input: str = None):
        session = await self.session_manager.get_or_create(session_id)
        await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.THINKING)
        await self.redis.publish(f"session:{session_id}:control", "STATE_THINKING")

        try:
            prompt_resp = await self.http_client.post(
                f"{self.personaplex_url}/prompt/build?session_id={session_id}",
                json={"session_id": session_id, "user_message": text_input or "Voice detected"}
            )
            prompt = prompt_resp.json()["prompt"]

            recall_resp = await self.http_client.post(
                f"{self.personaplex_url}/memory/retrieve",
                json={"user_id": session_data.get("user_id", "default"), "limit": 5}
            )
            if recall_resp.json().get("memories"):
                prompt += "\n\nRelevant Context:\n" + recall_resp.json()["memories"]

            await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.GENERATING)
            await self.redis.publish("session:update_prompt", json.dumps({
                "sessionId": session_id,
                "prompt": prompt
            }))
            logger.info("Turn coordinated", session_id=session_id)
        except Exception as e:
            logger.error("Turn coordination failed", error=str(e), session_id=session_id)
            await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.LISTENING)

    async def trigger_interrupt(self, session_id: str):
        logger.info("Global interrupt triggered", session_id=session_id)
        await self.redis.publish(f"session:{session_id}:control", "INTERRUPT")
        await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.INTERRUPTING)
        await self.redis.publish(f"session:{session_id}:events", json.dumps({"type": "interrupted"}))
        await asyncio.sleep(0.1)
        await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.LISTENING)

    async def stream_text_response(
        self,
        session_id: str,
        user_message: str,
        language: str = "en",
    ):
        """
        Stream a text response via Redis pub/sub.
        
        Publishes to session:{session_id}:tokens with format:
        - {"type": "token", "content": "..."} for each token
        - {"type": "done", "total_ms": 1234} when complete
        - {"type": "error", "message": "..."} on error
        """
        t0 = asyncio.get_event_loop().time()
        
        # Get endpoint for language
        endpoint = VLLM_ENDPOINTS.get(language, VLLM_ENDPOINTS["en"])
        system_prompt = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        body = {
            "model": endpoint["model"],
            "messages": messages,
            "stream": True,
            "max_tokens": 256,
            "temperature": 0.6,
            "top_p": 0.9,
            "repetition_penalty": 1.1,
            "presence_penalty": 0.3,
        }
        
        await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.GENERATING)
        
        try:
            full_response = ""
            async with self.http_client.stream(
                "POST",
                f"http://{endpoint['host']}:{endpoint['port']}/v1/chat/completions",
                json=body,
                headers={"Authorization": "Bearer EMPTY"},
            ) as response:
                if response.status_code != 200:
                    error_msg = f"vLLM error (HTTP {response.status_code})"
                    logger.error(error_msg, session_id=session_id)
                    await self.redis.publish(
                        f"session:{session_id}:tokens",
                        json.dumps({"type": "error", "message": error_msg}),
                    )
                    return
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    lines = buffer.split("\n")
                    buffer = lines.pop() or ""
                    
                    for line in lines:
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            total_ms = (asyncio.get_event_loop().time() - t0) * 1000
                            await self.redis.publish(
                                f"session:{session_id}:tokens",
                                json.dumps({"type": "done", "total_ms": round(total_ms, 1)}),
                            )
                            logger.info(
                                "Stream complete",
                                session_id=session_id,
                                total_ms=round(total_ms, 1),
                                chars=len(full_response),
                            )
                            await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.LISTENING)
                            return
                        
                        try:
                            parsed = json.loads(data_str)
                            token = parsed.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if token:
                                full_response += token
                                await self.redis.publish(
                                    f"session:{session_id}:tokens",
                                    json.dumps({"type": "token", "content": token}),
                                )
                        except json.JSONDecodeError:
                            pass
            
        except Exception as e:
            logger.error("Stream failed", error=str(e), session_id=session_id)
            await self.redis.publish(
                f"session:{session_id}:tokens",
                json.dumps({"type": "error", "message": str(e)}),
            )
            await self.redis.hset(f"session:{session_id}:meta", "state", SessionState.LISTENING)


if __name__ == "__main__":
    pass
