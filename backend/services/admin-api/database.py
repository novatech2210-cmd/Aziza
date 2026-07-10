"""
Qube Admin API — Database
asyncpg connection pool with graceful no-op when DB_DSN is not configured.
"""

from __future__ import annotations
import asyncpg  # type: ignore
import config

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """Call once at startup if DB_DSN is set."""
    global _pool
    if config.DB_DSN:
        try:
            _pool = await asyncpg.create_pool(config.DB_DSN, min_size=2, max_size=10)
        except Exception as exc:
            print(f"[DB] Pool creation failed (DB features disabled): {exc}")
            _pool = None


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_conn() -> asyncpg.Connection:
    if _pool is None:
        raise RuntimeError("Database pool not initialised (DB_DSN not set)")
    return await _pool.acquire()


async def release_conn(conn: asyncpg.Connection) -> None:
    if _pool and conn:
        await _pool.release(conn)
