import asyncio
import time
import os
import redis.asyncio as aioredis
from typing import Dict

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# Worker registry — single source of truth
WORKER_REGISTRY: Dict[str, dict] = {}
# Example format: { "worker-01": { "status": "idle"|"busy", "session_id": None|str, "gpu": "0", "last_heartbeat": float } }

async def get_available_worker() -> str | None:
    """
    Returns worker_id of an idle worker, or None if all workers are busy.
    Uses least-recently-used selection to distribute sessions evenly.
    """
    idle = [
        (wid, w) for wid, w in WORKER_REGISTRY.items()
        if w["status"] == "idle"
        and (time.time() - w["last_heartbeat"]) < 15  # Only healthy workers
    ]
    if not idle:
        return None
    # LRU: pick worker with oldest last_session_end time
    return min(idle, key=lambda x: x[1].get("last_session_end", 0))[0]

async def assign_session(session_id: str, worker_id: str, redis: aioredis.Redis) -> None:
    WORKER_REGISTRY[worker_id]["status"] = "busy"
    WORKER_REGISTRY[worker_id]["session_id"] = session_id
    await redis.publish(f"orchestrator:session:assign:{worker_id}", session_id)

async def release_session(worker_id: str) -> None:
    WORKER_REGISTRY[worker_id]["status"] = "idle"
    WORKER_REGISTRY[worker_id]["session_id"] = None
    WORKER_REGISTRY[worker_id]["last_session_end"] = time.time()
    # Check if sessions are queued
    # await process_session_queue()

async def notify_client_of_disruption(session_id: str):
    print(f"Notifying client of disruption for session: {session_id}")

async def handle_dead_worker(worker_id: str, redis: aioredis.Redis):
    session_id = WORKER_REGISTRY[worker_id].get("session_id")
    del WORKER_REGISTRY[worker_id]
    if session_id:
        # Attempt reassignment to another idle worker
        new_worker = await get_available_worker()
        if new_worker:
            await assign_session(session_id, new_worker, redis)
        else:
            await notify_client_of_disruption(session_id)

async def heartbeat_monitor(redis: aioredis.Redis):
    """Run as background task. Checks every 5s."""
    while True:
        await asyncio.sleep(5)
        now = time.time()
        for worker_id, worker in list(WORKER_REGISTRY.items()):
            if now - worker["last_heartbeat"] > 15:
                await handle_dead_worker(worker_id, redis)

async def main():
    redis = await aioredis.from_url(REDIS_URL)
    
    # Start heartbeat monitor
    asyncio.create_task(heartbeat_monitor(redis))
    
    pubsub = redis.pubsub()
    await pubsub.subscribe("orchestrator:worker:heartbeat")
    await pubsub.subscribe("orchestrator:session:release")
    
    print("Orchestrator started, listening for events...")
    
    async for message in pubsub.listen():
        if message["type"] == "message":
            channel = message["channel"].decode()
            data = message["data"].decode()
            
            if channel == "orchestrator:worker:heartbeat":
                # Assuming data is worker_id string for simplicity, actually should be JSON
                import json
                try:
                    payload = json.loads(data)
                    wid = payload.get("worker_id")
                    if wid:
                        if wid not in WORKER_REGISTRY:
                            WORKER_REGISTRY[wid] = {"status": "idle", "last_heartbeat": time.time(), "session_id": None}
                        else:
                            WORKER_REGISTRY[wid]["last_heartbeat"] = time.time()
                except json.JSONDecodeError:
                    pass
                    
            elif channel == "orchestrator:session:release":
                wid = data
                if wid in WORKER_REGISTRY:
                    await release_session(wid)

if __name__ == "__main__":
    asyncio.run(main())
