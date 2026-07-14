import torch
import asyncio
import logging
import time
from typing import AsyncGenerator
from moshi_engine import MoshiEngine
from gpu_scheduler import GPUScheduler

logger = logging.getLogger("MoshiInference")

class MoshiInferenceService:
    def __init__(self, device: str = "cuda"):
        self.engine = MoshiEngine(device=device)
        self.scheduler = GPUScheduler()
        self.active_tasks: dict[str, asyncio.Task] = {}
        self._task_cleanup_interval = 30  # seconds
        self._last_cleanup = time.time()
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """Background task to clean up completed inference tasks."""
        async def _cleanup_loop():
            while True:
                await asyncio.sleep(self._task_cleanup_interval)
                now = time.time()
                completed = [
                    sid for sid, task in self.active_tasks.items()
                    if task.done()
                ]
                for sid in completed:
                    task = self.active_tasks.pop(sid)
                    try:
                        task.result()
                    except Exception as e:
                        logger.debug(f"Completed task for {sid} had error: {e}")
                if completed:
                    logger.debug(f"Cleaned up {len(completed)} completed tasks")
                self._last_cleanup = now
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_cleanup_loop())
        except RuntimeError:
            pass

    async def process_audio_stream(
        self,
        session_id: str,
        audio_chunk: bytes
    ) -> dict:
        """Process a single audio chunk from the duplex stream."""
        if session_id not in self.scheduler.active_sessions:
            await self.scheduler.acquire_slot(session_id)

        stream = self.scheduler.cuda_streams.get(session_id)
        
        try:
            if stream:
                with torch.cuda.stream(stream):
                    result = await self.engine.step(session_id, audio_chunk)
            else:
                result = await self.engine.step(session_id, audio_chunk)
            return result
        except Exception as e:
            logger.error(f"Inference error for session {session_id}: {e}")
            return {"audio": None, "text": ""}

    async def process_text_stream(
        self,
        session_id: str,
        text_str: str
    ) -> dict:
        """Process a text message directly."""
        if session_id not in self.scheduler.active_sessions:
            await self.scheduler.acquire_slot(session_id)

        stream = self.scheduler.cuda_streams.get(session_id)
        
        try:
            if stream:
                with torch.cuda.stream(stream):
                    result = await self.engine.step_text(session_id, text_str)
            else:
                result = await self.engine.step_text(session_id, text_str)
            return result
        except Exception as e:
            logger.error(f"Text inference error for session {session_id}: {e}")
            return {"audio": None, "text": ""}

    async def cancel(self, session_id: str):
        """Stop inference for a session (Interruption)."""
        logger.info(f"Cancelling inference for session {session_id}")
        self.engine.reset_session(session_id)
        await self.scheduler.release_slot(session_id)
        
        if session_id in self.active_tasks:
            self.active_tasks[session_id].cancel()
            del self.active_tasks[session_id]

    def get_gpu_status(self):
        return {
            "memory_allocated": torch.cuda.memory_allocated(),
            "memory_reserved": torch.cuda.memory_reserved(),
            "scheduler": self.scheduler.get_stats(),
        }
