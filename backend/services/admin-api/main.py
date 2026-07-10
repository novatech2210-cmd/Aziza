"""
Qube Admin API — Entry Point
FastAPI app with lifespan, CORS, and the admin router.
Replaces the previous monolithic admin_api.py.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import database as db
from backend.services.metrics import run_collector
from routers.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.init_pool()
    collector_task = asyncio.create_task(run_collector())
    yield
    # Shutdown
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass
    await db.close_pool()


app = FastAPI(
    title="Qube Admin API",
    version="4.1.0",
    description="Admin dashboard API for AZIZA — GPU stats, sessions, RAG, audit logs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health (public) ──────────────────────────────────────────────────────────
from backend.services.gpu import GPU_AVAILABLE  # noqa: E402


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "service": "admin",
        "gpu_available": GPU_AVAILABLE,
        "db_connected": db._pool is not None,
    }


# ── Admin router ─────────────────────────────────────────────────────────────
app.include_router(admin_router)


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=False,
        log_level="info",
    )
