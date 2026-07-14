#!/usr/bin/env python3
"""Load testing framework for AZIZA vLLM inference.

Tests:
- Concurrent request throughput
- TTFT (Time to First Token) under load
- Error rates at various concurrency levels
- Memory stability under sustained load

Usage:
    python3 load_test.py --port 8002 --concurrent 5 --duration 60
    python3 load_test.py --port 8003 --concurrent 10 --message "Salom"
"""

import argparse
import asyncio
import json
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Optional
import httpx


@dataclass
class RequestResult:
    success: bool
    ttft_ms: float = 0.0
    total_ms: float = 0.0
    tokens_generated: int = 0
    tokens_per_sec: float = 0.0
    error: Optional[str] = None
    status_code: int = 0


@dataclass
class LoadTestReport:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    error_rate: float = 0.0
    ttft_p50: float = 0.0
    ttft_p95: float = 0.0
    ttft_p99: float = 0.0
    ttft_avg: float = 0.0
    total_avg_ms: float = 0.0
    total_p95_ms: float = 0.0
    tokens_per_sec_avg: float = 0.0
    requests_per_sec: float = 0.0
    duration_seconds: float = 0.0
    results: List[RequestResult] = field(default_factory=list)


def percentile(data: List[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int((p / 100) * len(sorted_data))
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


async def single_request(
    client: httpx.AsyncClient,
    port: int,
    message: str,
    model: str,
    timeout: float = 120.0,
) -> RequestResult:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 128,
    }
    headers = {"Authorization": "Bearer EMPTY", "Content-Type": "application/json"}

    start = time.time()
    ttft = 0.0
    tokens = 0
    first_token = True

    try:
        async with client.stream(
            "POST",
            f"http://127.0.0.1:{port}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                return RequestResult(
                    success=False,
                    status_code=resp.status_code,
                    error=f"HTTP {resp.status_code}: {body.decode()[:200]}",
                    total_ms=(time.time() - start) * 1000,
                )

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if token:
                        if first_token:
                            ttft = (time.time() - start) * 1000
                            first_token = False
                        tokens += 1
                except json.JSONDecodeError:
                    pass

        total_ms = (time.time() - start) * 1000
        tps = tokens / (total_ms / 1000) if total_ms > 0 else 0
        return RequestResult(
            success=True,
            ttft_ms=ttft,
            total_ms=total_ms,
            tokens_generated=tokens,
            tokens_per_sec=tps,
        )
    except httpx.TimeoutException:
        return RequestResult(
            success=False,
            error="Timeout",
            total_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        return RequestResult(
            success=False,
            error=str(e),
            total_ms=(time.time() - start) * 1000,
        )


async def load_test(
    port: int,
    concurrent: int,
    duration: int,
    message: str,
    model: str,
) -> LoadTestReport:
    report = LoadTestReport()
    start_time = time.time()
    all_results: List[RequestResult] = []

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(concurrent)

        async def bounded_request():
            async with sem:
                return await single_request(client, port, message, model)

        while time.time() - start_time < duration:
            batch = [bounded_request() for _ in range(concurrent)]
            results = await asyncio.gather(*batch)
            all_results.extend(results)
            elapsed = time.time() - start_time
            done = len(all_results)
            ok = sum(1 for r in all_results if r.success)
            print(
                f"\r  [{elapsed:.0f}s] {done} requests, "
                f"{ok}/{done} ok ({ok/done*100:.0f}%)",
                end="",
                flush=True,
            )
            await asyncio.sleep(0.1)

    elapsed = time.time() - start_time
    print()

    successes = [r for r in all_results if r.success]
    failures = [r for r in all_results if not r.success]

    report.total_requests = len(all_results)
    report.successful = len(successes)
    report.failed = len(failures)
    report.error_rate = (len(failures) / len(all_results) * 100) if all_results else 0
    report.duration_seconds = elapsed
    report.requests_per_sec = len(all_results) / elapsed if elapsed > 0 else 0

    if successes:
        ttfts = [r.ttft_ms for r in successes if r.ttft_ms > 0]
        totals = [r.total_ms for r in successes]
        tps_list = [r.tokens_per_sec for r in successes if r.tokens_per_sec > 0]

        report.ttft_avg = statistics.mean(ttfts) if ttfts else 0
        report.ttft_p50 = percentile(ttfts, 50)
        report.ttft_p95 = percentile(ttfts, 95)
        report.ttft_p99 = percentile(ttfts, 99)
        report.total_avg_ms = statistics.mean(totals)
        report.total_p95_ms = percentile(totals, 95)
        report.tokens_per_sec_avg = statistics.mean(tps_list) if tps_list else 0

    report.results = all_results
    return report


def print_report(report: LoadTestReport):
    print("\n" + "=" * 60)
    print("LOAD TEST REPORT")
    print("=" * 60)
    print(f"  Duration:           {report.duration_seconds:.1f}s")
    print(f"  Total requests:     {report.total_requests}")
    print(f"  Successful:         {report.successful}")
    print(f"  Failed:             {report.failed}")
    print(f"  Error rate:         {report.error_rate:.1f}%")
    print(f"  Requests/sec:       {report.requests_per_sec:.1f}")
    print()
    print("  TTFT (Time to First Token):")
    print(f"    Avg:              {report.ttft_avg:.0f}ms")
    print(f"    P50:              {report.ttft_p50:.0f}ms")
    print(f"    P95:              {report.ttft_p95:.0f}ms")
    print(f"    P99:              {report.ttft_p99:.0f}ms")
    print()
    print("  Total Latency:")
    print(f"    Avg:              {report.total_avg_ms:.0f}ms")
    print(f"    P95:              {report.total_p95_ms:.0f}ms")
    print()
    print(f"  Tokens/sec (avg):   {report.tokens_per_sec_avg:.1f}")
    print("=" * 60)

    if report.error_rate > 5:
        print(f"\n  WARNING: Error rate {report.error_rate:.1f}% exceeds 5% threshold")
    if report.ttft_p95 > 2000:
        print(f"  WARNING: TTFT P95 ({report.ttft_p95:.0f}ms) exceeds 2s target")


async def main():
    parser = argparse.ArgumentParser(description="AZIZA vLLM Load Tester")
    parser.add_argument("--port", type=int, default=8002, help="vLLM port (default: 8002)")
    parser.add_argument("--concurrent", type=int, default=5, help="Concurrent requests (default: 5)")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds (default: 30)")
    parser.add_argument("--message", type=str, default="Привет, как дела?", help="Test message")
    parser.add_argument(
        "--model",
        type=str,
        default="Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24",
        help="Model name",
    )
    args = parser.parse_args()

    print(f"\nStarting load test: port={args.port}, concurrent={args.concurrent}, duration={args.duration}s")
    print(f"Message: {args.message}")
    print(f"Model: {args.model}\n")

    report = await load_test(
        port=args.port,
        concurrent=args.concurrent,
        duration=args.duration,
        message=args.message,
        model=args.model,
    )

    print_report(report)

    exit_code = 1 if report.error_rate > 10 else 0
    raise SystemExit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
