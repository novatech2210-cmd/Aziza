"""
Qube Backend — vLLM Auto-Launcher
Spawns vLLM OpenAI-compatible servers as subprocesses.
Waits until each server is healthy before returning.
"""

import asyncio
import os
import subprocess
import sys
import time

import httpx

import config


_processes: list[subprocess.Popen] = []


def _build_vllm_cmd(model: str, port: int) -> list[str]:
    return [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model,
        "--dtype", config.VLLM_DTYPE,
        "--gpu-memory-utilization", str(config.VLLM_GPU_MEMORY_UTIL),
        "--max-num-seqs", str(config.VLLM_MAX_NUM_SEQS),
        "--max-model-len", str(config.VLLM_MAX_MODEL_LEN),
        "--enable-chunked-prefill",
        "--host", "0.0.0.0",
        "--port", str(port),
    ]


async def _wait_for_health(url: str, label: str, timeout: int = 600):
    """Poll /v1/models until the server responds or timeout."""
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() - start < timeout:
            try:
                resp = await client.get(f"{url}/v1/models")
                if resp.status_code == 200:
                    elapsed = time.monotonic() - start
                    print(f"[VLLM] {label} ready in {elapsed:.1f}s")
                    return
            except Exception:
                pass
            await asyncio.sleep(2)
    print(f"[VLLM] WARNING: {label} did not become healthy within {timeout}s — continuing anyway")


async def _is_already_running(url: str) -> bool:
    """Check if a vLLM server is already responding."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{url}/v1/models")
            return resp.status_code == 200
    except Exception:
        return False


async def launch_vllm_servers():
    """Start vLLM servers if LAUNCH_VLLM is enabled and they aren't already running."""
    if not config.LAUNCH_VLLM:
        print("[VLLM] Auto-launch disabled (LAUNCH_VLLM=false)")
        return

    servers = [
        {
            "label": f"EN/RU — {config.LLM_MODEL_EN}",
            "model": config.LLM_MODEL_EN,
            "port": config.LLM_PORT_EN,
            "gpu": config.LLM_GPU_EN,
            "url": config.LLM_URL_EN,
        },
        {
            "label": f"UZ — {config.LLM_MODEL_UZ}",
            "model": config.LLM_MODEL_UZ,
            "port": config.LLM_PORT_UZ,
            "gpu": config.LLM_GPU_UZ,
            "url": config.LLM_URL_UZ,
        },
    ]

    for srv in servers:
        if await _is_already_running(srv["url"]):
            print(f"[VLLM] {srv['label']} already running on port {srv['port']} — skipping")
            continue

        cmd = _build_vllm_cmd(srv["model"], srv["port"])
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = srv["gpu"]

        print(f"[VLLM] Launching {srv['label']} on GPU {srv['gpu']}, port {srv['port']}...")
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        _processes.append(proc)

    # Wait for all servers to become healthy (in parallel)
    health_tasks = []
    for srv in servers:
        health_tasks.append(_wait_for_health(srv["url"], srv["label"]))
    await asyncio.gather(*health_tasks)


def stop_vllm_servers():
    """Terminate all vLLM subprocesses."""
    for proc in _processes:
        if proc.poll() is None:
            print(f"[VLLM] Stopping PID {proc.pid}")
            proc.terminate()
    # Give them a moment, then force-kill
    for proc in _processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    _processes.clear()
