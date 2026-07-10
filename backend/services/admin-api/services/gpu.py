"""
Qube Admin API — GPU service
Reads live GPU stats via pynvml with graceful fallback.
"""

from __future__ import annotations

try:
    import pynvml  # type: ignore
    pynvml.nvmlInit()
    GPU_AVAILABLE: bool = True
except Exception:
    GPU_AVAILABLE = False


def read_gpu_stats() -> list[dict]:
    """Return a list of per-GPU stat dicts. Empty list if no GPU / pynvml unavailable."""
    if not GPU_AVAILABLE:
        return []
    stats = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            try:
                temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = None
            # nvmlDeviceGetName returns bytes on older pynvml, str on newer
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            stats.append(
                {
                    "gpu_id": i,
                    "name": name,
                    "vram_used_mb": round(mem.used / 1_048_576),
                    "vram_total_mb": round(mem.total / 1_048_576),
                    "utilization_pct": util.gpu,
                    "memory_pct": util.memory,
                    "temperature_c": temp,
                }
            )
    except Exception as exc:
        # Don't crash the whole request on GPU read errors
        stats.append({"error": str(exc)})
    return stats
