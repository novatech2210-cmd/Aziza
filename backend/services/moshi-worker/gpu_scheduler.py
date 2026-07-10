# pyrefly: ignore [missing-import]
import torch
import asyncio
import time
import logging

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
            "gpu_util_percent": util.gpu,
            "temperature_c": temp
        })
    return stats


class GPUScheduler:
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.active_sessions: dict[str, dict] = {}
        self.cuda_streams: dict[str, torch.cuda.Stream] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def acquire_slot(self, session_id: str) -> bool:
        """Wait for a GPU slot and create a dedicated CUDA stream."""
        await self.semaphore.acquire()
        try:
            if torch.cuda.is_available():
                # On L40S, we can have many streams
                stream = torch.cuda.Stream()
                self.cuda_streams[session_id] = stream
            self.active_sessions[session_id] = {"start_time": time.time()}
            logger.info(f"Acquired GPU slot for {session_id}. Active: {len(self.active_sessions)}")
            return True
        except Exception as e:
            self.semaphore.release()
            logger.error(f"Failed to acquire GPU slot for {session_id}: {e}")
            return False

    async def release_slot(self, session_id: str):
        """Release the GPU slot and synchronize the stream."""
        if stream := self.cuda_streams.pop(session_id, None):
            try:
                # Ensure all work on this stream is done
                stream.synchronize()
            except Exception as e:
                logger.error(f"Error synchronizing stream for {session_id}: {e}")
        
        if session_id in self.active_sessions:
            self.active_sessions.pop(session_id)
            self.semaphore.release()
            logger.info(f"Released GPU slot for {session_id}. Active: {len(self.active_sessions)}")

    def get_stats(self):
        stats = {
            "gpu_memory_allocated_gb": torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0,
            "gpu_memory_reserved_gb": torch.cuda.memory_reserved() / 1024**3 if torch.cuda.is_available() else 0,
            "active_sessions": len(self.active_sessions),
        }
        if GPU_AVAILABLE:
            stats["nvml_stats"] = read_gpu_stats()
        return stats
