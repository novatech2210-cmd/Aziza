"""
Qube Phase 4 — Admin Dashboard API
Port: 8012

Proxies stats from the Phase 3 chat gateway and provides GPU / log / RAG endpoints.
All admin endpoints require JWT with role="admin".
"""

import os
import json
import asyncio
import time
from datetime import datetime, timezone
from collections import deque
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8010")

bearer_scheme = HTTPBearer()

# In-memory stores for history (last 60 data points)
gpu_history: deque = deque(maxlen=60)
latency_history: deque = deque(maxlen=60)
error_log: deque = deque(maxlen=500)

# ---------------------------------------------------------------------------
# GPU helpers (pynvml — optional, graceful fallback)
# ---------------------------------------------------------------------------
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False


def _read_gpu_stats() -> list[dict]:
    if not GPU_AVAILABLE:
        return []
    stats = []
    count = pynvml.nvmlDeviceGetCount()
    for i in range(count):
        h = pynvml.nvmlDeviceGetHandleByIndex(i)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
        try:
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            temp = None
        stats.append({
            "gpu_id": i,
            "name": pynvml.nvmlDeviceGetName(h),
            "vram_used_mb": round(mem.used / 1048576),
            "vram_total_mb": round(mem.total / 1048576),
            "utilization_pct": util.gpu,
            "memory_pct": util.memory,
            "temperature_c": temp,
        })
    return stats


# ---------------------------------------------------------------------------
# Background collector
# ---------------------------------------------------------------------------
async def _collect_stats():
    """Collect GPU + latency stats every second."""
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            ts = datetime.now(timezone.utc).isoformat()

            # GPU
            gpu = _read_gpu_stats()
            gpu_history.append({"ts": ts, "gpus": gpu})

            # Latency from gateway
            try:
                r = await client.get(f"{GATEWAY_URL}/admin/metrics")
                if r.status_code == 200:
                    latency_history.append({"ts": ts, **r.json()})
            except Exception:
                latency_history.append({"ts": ts, "p50": None, "p95": None, "p99": None})

            await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_collect_stats())
    yield
    task.cancel()


app = FastAPI(title="Qube Admin API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_admin(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    payload = decode_token(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def _ws_verify_admin(token: str) -> bool:
    """Verify a token is admin for WebSocket connections."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("role") == "admin"
    except JWTError:
        return False


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "admin", "gpu_available": GPU_AVAILABLE}


# ---------------------------------------------------------------------------
# Session endpoints (proxy to gateway)
# ---------------------------------------------------------------------------
@app.get("/admin/sessions")
async def get_sessions(_=Depends(require_admin)):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{GATEWAY_URL}/admin/sessions")
            return r.json()
        except Exception as e:
            raise HTTPException(502, detail=f"Gateway unreachable: {e}")


@app.delete("/admin/sessions/{session_id}")
async def terminate_session(session_id: str, _=Depends(require_admin)):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.delete(f"{GATEWAY_URL}/admin/sessions/{session_id}")
            return r.json()
        except Exception as e:
            raise HTTPException(502, detail=f"Gateway unreachable: {e}")


@app.get("/admin/sessions/stats")
async def session_stats(_=Depends(require_admin)):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{GATEWAY_URL}/admin/sessions")
            sessions = r.json() if r.status_code == 200 else []
            return {
                "active": len(sessions) if isinstance(sessions, list) else 0,
                "peak_today": len(sessions) if isinstance(sessions, list) else 0,
                "avg_duration_s": 0,
            }
        except Exception:
            return {"active": 0, "peak_today": 0, "avg_duration_s": 0}


# ---------------------------------------------------------------------------
# GPU endpoints
# ---------------------------------------------------------------------------
@app.get("/admin/gpu")
async def gpu_stats(_=Depends(require_admin)):
    return _read_gpu_stats()


@app.get("/admin/gpu/history")
async def gpu_stats_history(_=Depends(require_admin)):
    return list(gpu_history)


# ---------------------------------------------------------------------------
# Latency endpoints
# ---------------------------------------------------------------------------
@app.get("/admin/latency")
async def latency(_=Depends(require_admin)):
    if latency_history:
        return latency_history[-1]
    return {"p50": None, "p95": None, "p99": None}


@app.get("/admin/latency/history")
async def latency_hist(_=Depends(require_admin)):
    return list(latency_history)


@app.get("/admin/latency/heatmap")
async def latency_heatmap(_=Depends(require_admin)):
    """Proxy heatmap data from the gateway."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{GATEWAY_URL}/admin/latency/heatmap")
            return r.json()
        except Exception as e:
            raise HTTPException(502, detail=f"Gateway unreachable: {e}")


# ---------------------------------------------------------------------------
# Error endpoints
# ---------------------------------------------------------------------------
@app.get("/admin/errors")
async def errors(_=Depends(require_admin)):
    # Merge local error_log with gateway errors
    gateway_errors = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{GATEWAY_URL}/admin/errors")
            if r.status_code == 200:
                gateway_errors = r.json()
    except Exception:
        pass
    all_errors = list(error_log) + gateway_errors
    all_errors.sort(key=lambda e: e.get("ts_epoch", 0), reverse=True)
    return all_errors[:500]


@app.get("/admin/errors/rate")
async def error_rate(_=Depends(require_admin)):
    now = time.time()
    minute_ago = now - 60
    recent = [e for e in error_log if e.get("ts_epoch", 0) > minute_ago]
    return {"errors_per_minute": len(recent)}


# ---------------------------------------------------------------------------
# RAG endpoints (proxy to gateway)
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    texts: list[str]


@app.get("/admin/rag/stats")
async def rag_stats(_=Depends(require_admin)):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{GATEWAY_URL}/admin/rag/stats")
            return r.json()
        except Exception:
            return {"doc_count": 0, "index_size_bytes": 0, "last_updated": None}


@app.post("/admin/rag/ingest")
async def rag_ingest(req: IngestRequest, _=Depends(require_admin)):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(f"{GATEWAY_URL}/admin/rag/ingest", json={"texts": req.texts})
            return r.json()
        except Exception as e:
            raise HTTPException(502, detail=f"Gateway unreachable: {e}")


@app.delete("/admin/rag/clear")
async def rag_clear(_=Depends(require_admin)):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.delete(f"{GATEWAY_URL}/admin/rag/clear")
            return r.json()
        except Exception as e:
            raise HTTPException(502, detail=f"Gateway unreachable: {e}")


# ---------------------------------------------------------------------------
# Log endpoints
# ---------------------------------------------------------------------------
@app.get("/admin/logs")
async def logs(
    level: str = Query(None),
    service: str = Query(None),
    limit: int = Query(100),
    _=Depends(require_admin),
):
    result = list(error_log)
    if level:
        result = [e for e in result if e.get("level", "").upper() == level.upper()]
    if service:
        result = [e for e in result if e.get("service", "") == service]
    return result[-limit:]


# ---------------------------------------------------------------------------
# WebSocket — live admin stats (push every 1s)
# ---------------------------------------------------------------------------
@app.websocket("/admin/ws/stats")
async def ws_admin_stats(ws: WebSocket):
    # Auth via query param: ?token=xxx
    token = ws.query_params.get("token", "")
    if not _ws_verify_admin(token):
        await ws.close(code=4003, reason="Forbidden")
        return

    await ws.accept()
    try:
        while True:
            data = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "gpu": _read_gpu_stats(),
                "sessions": None,
                "latency": dict(latency_history[-1]) if latency_history else {},
                "error_rate": 0,
            }
            # Try to fetch live session count
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(f"{GATEWAY_URL}/admin/sessions")
                    if r.status_code == 200:
                        sessions = r.json()
                        data["sessions"] = {
                            "active": len(sessions) if isinstance(sessions, list) else 0,
                        }
            except Exception:
                pass

            # Get error rate from gateway metrics
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(f"{GATEWAY_URL}/admin/metrics")
                    if r.status_code == 200:
                        metrics = r.json()
                        data["error_rate"] = metrics.get("error_rate", 0)
                        # Also update latency from gateway
                        if not data["latency"]:
                            data["latency"] = {"p50": metrics.get("p50", 0), "p95": metrics.get("p95", 0)}
            except Exception:
                now = time.time()
                recent_errors = [e for e in error_log if e.get("ts_epoch", 0) > now - 60]
                data["error_rate"] = len(recent_errors)

            await ws.send_json(data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin_api:app", host="0.0.0.0", port=8012, reload=True)
