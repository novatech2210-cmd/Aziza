# pyrefly: ignore [missing-import]
import torch
import asyncio
import time
import logging
import os

logger = logging.getLogger("GPUScheduler")

try:
    # pyrefly: ignore [missing-import]
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
    logger.info(f"[GPU] pynvml initialized — {pynvml.nvmlDeviceGetCount()} GPU(s) detected")
except Exception:
    GPU_AVAILABLE = False
    logger.info("[GPU] pynvml not available — GPU monitoring disabled")


def read_gpu_stats() -> list[dict]:
    """Read current GPU stats from NVML."""
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
        
        name = pynvml.nvmlDeviceGetName(h)
        if isinstance(name, bytes):
            name = name.decode('utf-8')
            
        stats.append({
            "gpu_id": i,
            "name": name,
            "vram_used_mb": round(mem.used / 1048576),
            "vram_total_mb": round(mem.total / 1048576),
            "vram_free_mb": round(mem.free / 1048576),
            "gpu_util_percent": util.gpu,
            "temperature_c": temp
        })
    return stats


def get_vram_usage() -> dict:
    """Get current VRAM usage for scheduling decisions."""
    if not GPU_AVAILABLE:
        return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "utilization": 0}
    try:
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
        return {
            "total_mb": round(mem.total / 1048576),
            "used_mb": round(mem.used / 1048576),
            "free_mb": round(mem.free / 1048576),
            "utilization": util.gpu,
        }
    except Exception:
        return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "utilization": 0}


class GPUScheduler:
    def __init__(self, max_concurrent: int = None):
        self.max_concurrent = max_concurrent or int(os.getenv("GPU_MAX_CONCURRENT", "12"))
        self.active_sessions: dict[str, dict] = {}
        self.cuda_streams: dict[str, torch.cuda.Stream] = {}
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self._min_free_vram_mb = int(os.getenv("GPU_MIN_FREE_VRAM_MB", "2048"))

    async def acquire_slot(self, session_id: str) -> bool:
        """Wait for a GPU slot and create a dedicated CUDA stream."""
        await self.semaphore.acquire()
        try:
            # Check VRAM availability
            vram = get_vram_usage()
            if vram["free_mb"] < self._min_free_vram_mb and len(self.active_sessions) > 0:
                logger.warning(
                    f"Low VRAM ({vram['free_mb']}MB free) for {session_id}. "
                    f"Active sessions: {len(self.active_sessions)}"
                )

            if torch.cuda.is_available():
                stream = torch.cuda.Stream()
                self.cuda_streams[session_id] = stream
            self.active_sessions[session_id] = {
                "start_time": time.time(),
                "vram_at_acquire": vram.get("used_mb", 0),
            }
            logger.info(
                f"Acquired GPU slot for {session_id}. "
                f"Active: {len(self.active_sessions)}/{self.max_concurrent}. "
                f"VRAM: {vram.get('used_mb', '?')}MB used"
            )
            return True
        except Exception as e:
            self.semaphore.release()
            logger.error(f"Failed to acquire GPU slot for {session_id}: {e}")
            return False

    async def release_slot(self, session_id: str):
        """Release the GPU slot and synchronize the stream."""
        if stream := self.cuda_streams.pop(session_id, None):
            try:
                stream.synchronize()
            except Exception as e:
                logger.error(f"Error synchronizing stream for {session_id}: {e}")
        
        if session_id in self.active_sessions:
            session_info = self.active_sessions.pop(session_id)
            duration = time.time() - session_info["start_time"]
            self.semaphore.release()
            logger.info(
                f"Released GPU slot for {session_id} after {duration:.1f}s. "
                f"Active: {len(self.active_sessions)}/{self.max_concurrent}"
            )

    def get_stats(self):
        vram = get_vram_usage()
        stats = {
            "gpu_memory_allocated_gb": torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0,
            "gpu_memory_reserved_gb": torch.cuda.memory_reserved() / 1024**3 if torch.cuda.is_available() else 0,
            "active_sessions": len(self.active_sessions),
            "max_concurrent": self.max_concurrent,
            "slots_available": self.max_concurrent - len(self.active_sessions),
        }
        if GPU_AVAILABLE:
            stats["nvml_stats"] = read_gpu_stats()
            stats["vram"] = vram
        return stats
