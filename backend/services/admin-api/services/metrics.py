"""
Qube Admin API — Metrics service
Central in-memory store for sessions, tasks, errors, GPU/latency history.
"""

from __future__ import annotations

import asyncio
import math
import statistics
import time
from collections import deque
from datetime import datetime, timezone

import httpx  # type: ignore

import config
from backend.services.gpu import read_gpu_stats

# ---------------------------------------------------------------------------
# Live state stores (written to by other modules at runtime)
# ---------------------------------------------------------------------------

# session_id -> {ws, user_id, lang, started_at, ...}
active_sessions: dict[str, dict] = {}

# task tracking sets (task ids)
active_gen_tasks: set[str] = set()
active_tts_tasks: set[str] = set()

# Error log — deque of {"ts", "ts_epoch", "level", "service", "message"}
error_log: deque = deque(maxlen=500)

# Rolling history (last 60 data points)
gpu_history: deque = deque(maxlen=60)
latency_history: deque = deque(maxlen=60)

# Raw request latency samples (ms)
_latency_samples: deque = deque(maxlen=500)


def record_latency(ms: float) -> None:
    """Call from request middleware to record a response time."""
    _latency_samples.append(ms)


def _percentile(data: list[float], pct: float) -> float | None:
    if not data:
        return None
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * pct / 100
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def get_metrics() -> dict:
    """Return current latency percentiles + error rate."""
    samples = list(_latency_samples)
    now = time.time()
    minute_ago = now - 60
    recent_errors = [e for e in error_log if e.get("ts_epoch", 0) > minute_ago]

    # Prefer locally computed metrics; fall back to latest gateway push
    if samples:
        p50 = _percentile(samples, 50)
        p95 = _percentile(samples, 95)
        p99 = _percentile(samples, 99)
    elif latency_history:
        last = latency_history[-1]
        p50, p95, p99 = last.get("p50"), last.get("p95"), last.get("p99")
    else:
        p50 = p95 = p99 = None

    return {
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "error_rate": len(recent_errors),
        "active_sessions": len(active_sessions),
        "active_gen_tasks": len(active_gen_tasks),
        "active_tts_tasks": len(active_tts_tasks),
    }


def get_heatmap_data() -> list[dict]:
    """Return hourly latency averages from latency_history for a 24-h heatmap."""
    # Build per-hour buckets from history
    buckets: dict[int, list[float]] = {h: [] for h in range(24)}
    for entry in latency_history:
        try:
            ts = datetime.fromisoformat(entry["ts"])
            hour = ts.hour
            if entry.get("p50") is not None:
                buckets[hour].append(entry["p50"])
        except Exception:
            pass
    result = []
    for hour in range(24):
        vals = buckets[hour]
        result.append(
            {
                "hour": f"{hour:02d}:00",
                "latency": round(statistics.mean(vals), 1) if vals else None,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Background collector — called from lifespan
# ---------------------------------------------------------------------------
async def run_collector() -> None:
    """Collect GPU stats + gateway latency every second. Run as asyncio task."""
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            ts = datetime.now(timezone.utc).isoformat()

            # GPU
            try:
                gpu = read_gpu_stats()
            except Exception:
                gpu = []
            gpu_history.append({"ts": ts, "gpus": gpu})

            # Latency from gateway
            try:
                r = await client.get(f"{config.GATEWAY_URL}/admin/metrics")
                if r.status_code == 200:
                    latency_history.append({"ts": ts, **r.json()})
                else:
                    latency_history.append({"ts": ts, "p50": None, "p95": None, "p99": None})
            except Exception:
                latency_history.append({"ts": ts, "p50": None, "p95": None, "p99": None})

            await asyncio.sleep(1)
