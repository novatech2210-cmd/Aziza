#!/usr/bin/env python3
"""Quick connectivity check for vLLM services.

Tests each vLLM endpoint with a single request to verify availability.
No GPU required for the check itself (just HTTP reachability).

Usage:
    python3 quick_check.py
    python3 quick_check.py --ports 8002 8003
"""

import argparse
import asyncio
import json
import time
import httpx


async def check_endpoint(client: httpx.AsyncClient, port: int, timeout: float = 5.0) -> dict:
    result = {"port": port, "reachable": False, "status": None, "ms": 0, "error": None}
    start = time.time()
    try:
        resp = await client.get(
            f"http://127.0.0.1:{port}/v1/models",
            headers={"Authorization": "Bearer EMPTY"},
            timeout=timeout,
        )
        result["status"] = resp.status_code
        result["reachable"] = resp.status_code == 200
        result["ms"] = (time.time() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            result["models"] = [m.get("id", "unknown") for m in data.get("data", [])]
    except httpx.ConnectError:
        result["error"] = "Connection refused"
    except httpx.TimeoutException:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)
    return result


async def health_check(ports: list[int]):
    async with httpx.AsyncClient() as client:
        tasks = [check_endpoint(client, port) for port in ports]
        results = await asyncio.gather(*tasks)

    all_ok = True
    for r in results:
        status = "OK" if r["reachable"] else "FAIL"
        if not r["reachable"]:
            all_ok = False
        extra = ""
        if r.get("models"):
            extra = f" models={r['models']}"
        if r.get("error"):
            extra = f" error={r['error']}"
        print(f"  Port {r['port']}: {status} ({r['ms']:.0f}ms){extra}")

    return all_ok


async def main():
    parser = argparse.ArgumentParser(description="AZIZA vLLM Health Check")
    parser.add_argument("--ports", type=int, nargs="+", default=[8002, 8003])
    args = parser.parse_args()

    print("\nAZIZA vLLM Service Health Check")
    print("-" * 40)
    ok = await health_check(args.ports)
    print("-" * 40)
    print(f"\nResult: {'ALL OK' if ok else 'SOME FAILURES'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
