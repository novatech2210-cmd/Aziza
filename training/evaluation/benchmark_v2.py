import asyncio
import time
import json
import uuid
import struct
import logging
import argparse
import numpy as np
import redis.asyncio as redis
import subprocess
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Benchmark")

def get_gpu_metrics():
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total", "--format=csv,noheader,nounits"],
            universal_newlines=True
        )
        parts = output.strip().split(', ')
        return {
            "gpu_util": float(parts[0]),
            "mem_util": float(parts[1]),
            "mem_used_mb": float(parts[2]),
            "mem_total_mb": float(parts[3])
        }
    except Exception as e:
        return {}

async def run_session(redis_url, session_id, worker_id, input_pcm, start_delay=0):
    await asyncio.sleep(start_delay)
    r = redis.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"session:{session_id}:audio_out", f"session:{session_id}:text_out")
    
    CHUNK_SIZE = 960 
    
    first_token_time = None
    last_token_time = None
    latencies = []
    
    output_file = open(f"session_{session_id}_output.raw", "wb")
    text_log = open(f"session_{session_id}_text.log", "w")
    
    logger.info(f"Session {session_id} starting -> {worker_id}")
    
    start_time = time.time()
    
    async def send_audio():
        for i in range(0, len(input_pcm), CHUNK_SIZE):
            chunk = input_pcm[i:i+CHUNK_SIZE]
            if len(chunk) < CHUNK_SIZE:
                chunk += b'\x00' * (CHUNK_SIZE - len(chunk))
            await r.publish(f"moshi:worker:{worker_id}:audio_in:{session_id}", chunk)
            await asyncio.sleep(0.03) 
            
    send_task = asyncio.create_task(send_audio())
    
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            now = time.time()
            if msg:
                channel = msg["channel"].decode()
                data = msg["data"]
                
                if first_token_time is None:
                    first_token_time = now
                    logger.info(f"Session {session_id} TTFT: {(first_token_time - start_time)*1000:.2f} ms")
                
                if last_token_time is not None:
                    latencies.append(now - last_token_time)
                last_token_time = now
                
                if channel.endswith(":audio_out"):
                    output_file.write(data)
                elif channel.endswith(":text_out"):
                    text = data.decode('utf-8')
                    text_log.write(text + "\n")
                    text_log.flush()
            
            if send_task.done() and last_token_time and (now - last_token_time > 5.0):
                break
            
            if not last_token_time and (now - start_time > 15.0):
                logger.warning(f"Session {session_id} timeout waiting for first token.")
                break
                
    except asyncio.CancelledError:
        pass
    finally:
        output_file.close()
        text_log.close()
        await pubsub.unsubscribe()
        await r.aclose()
        
    avg_latency = (sum(latencies) / len(latencies)) * 1000 if latencies else 0
    max_pause = max(latencies) * 1000 if latencies else 0
    ttft = (first_token_time - start_time)*1000 if first_token_time else 0
    
    logger.info(f"Session {session_id} complete. TTFT: {ttft:.2f}ms, Avg Inter-token: {avg_latency:.2f}ms, Max Pause: {max_pause:.2f}ms")
    return {
        "ttft": ttft,
        "avg_latency": avg_latency,
        "max_pause": max_pause
    }

async def monitor_gpu(duration):
    start = time.time()
    metrics_log = []
    while time.time() - start < duration:
        m = get_gpu_metrics()
        if m:
            logger.info(f"GPU Util: {m['gpu_util']}%, Mem Util: {m['mem_util']}%, VRAM: {m['mem_used_mb']}/{m['mem_total_mb']} MB")
            metrics_log.append(m)
        await asyncio.sleep(2.0)
    return metrics_log

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=8)
    parser.add_argument("--redis", type=str, default="redis://localhost:6379")
    parser.add_argument("--audio_file", type=str, default="test_audio.raw")
    args = parser.parse_args()
    
    r = redis.from_url(args.redis)
    keys = await r.keys("moshi:workers:*")
    if not keys:
        logger.error("No moshi workers found in Redis!")
        return
    
    worker_info = await r.hgetall(keys[0])
    worker_id = worker_info[b'worker_id'].decode()
    logger.info(f"Using worker: {worker_id}")
    await r.aclose()
    
    if not os.path.exists(args.audio_file):
        logger.info(f"Generating dummy 10s audio file {args.audio_file}")
        sr = 16000
        t = np.linspace(0, 10, sr * 10)
        audio = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
        with open(args.audio_file, "wb") as f:
            f.write(audio.tobytes())
            
    with open(args.audio_file, "rb") as f:
        input_pcm = f.read()
        
    logger.info(f"Starting {args.sessions} concurrent sessions...")
    
    tasks = []
    monitor_task = asyncio.create_task(monitor_gpu(30))
    
    for i in range(args.sessions):
        session_id = f"test_session_{i}_{uuid.uuid4().hex[:4]}"
        tasks.append(run_session(args.redis, session_id, worker_id, input_pcm, start_delay=i*0.5))
        
    results = await asyncio.gather(*tasks)
    await monitor_task
    
    logger.info("--- Benchmark Results ---")
    for i, r in enumerate(results):
        logger.info(f"Session {i}: TTFT={r['ttft']:.2f}ms, Avg Latency={r['avg_latency']:.2f}ms, Max Pause={r['max_pause']:.2f}ms")

if __name__ == "__main__":
    asyncio.run(main())
