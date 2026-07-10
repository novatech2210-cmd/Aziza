#!/usr/bin/env python3
"""
Aziza TTFT (Time-To-First-Token) Benchmark
Measures latency from request to first token generation across all pipeline hops
"""
import asyncio
import json
import time
import uuid
import websockets
from datetime import datetime, timezone
from typing import Dict, List, Optional
import yaml
import sys
import os
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TelemetryLogger:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.session_id = str(uuid.uuid4())
        self.logs = []
        
    def log(self, event_type: str, data: Dict):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            **data
        }
        self.logs.append(entry)
        
    def save(self):
        log_file = os.path.join(self.log_dir, f"ttft_{self.session_id}.json")
        with open(log_file, 'w') as f:
            json.dump(self.logs, f, indent=2)
        return log_file

class TTFTBenchmark:
    def __init__(self, config_path: str = "benchmark_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.telemetry = TelemetryLogger(self.config['telemetry']['log_dir'])
        self.latencies = []
        self.target_ms = self.config['targets']['ttft_median_ms']
        
    async def measure_ttft(self, session_id: str, language: str = "ru") -> Optional[float]:
        """
        Measure TTFT for a single request
        Returns latency in milliseconds or None if failed
        """
        ws_url = self.config['environment']['websocket_url']
        
        # Timestamps for each hop
        timestamps = {
            "request_start": None,
            "websocket_send": None,
            "adapter_ingest": None,
            "moshi_inference_start": None,
            "first_token": None,
            "response_end": None
        }
        
        try:
            timestamps["request_start"] = time.time()
            
            async with websockets.connect(ws_url) as websocket:
                timestamps["websocket_send"] = time.time()
                
                # Send request
                request = {
                    "type": "start_session",
                    "session_id": session_id,
                    "language": language,
                    "persona": f"aziza_{language}",
                    "measure_ttft": True
                }
                
                await websocket.send(json.dumps(request))
                
                # Wait for first token response
                first_token_time = None
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "first_token":
                        timestamps["first_token"] = time.time()
                        first_token_time = timestamps["first_token"] - timestamps["request_start"]
                        break
                    elif data.get("type") == "error":
                        raise Exception(f"Server error: {data.get('message')}")
                    elif data.get("type") == "adapter_ingest":
                        timestamps["adapter_ingest"] = time.time()
                    elif data.get("type") == "moshi_inference_start":
                        timestamps["moshi_inference_start"] = time.time()
                
                # Clean shutdown
                await websocket.send(json.dumps({"type": "end_session", "session_id": session_id}))
                timestamps["response_end"] = time.time()
                
                # Calculate hop latencies
                hop_latencies = {
                    "websocket_connect_ms": (timestamps["websocket_send"] - timestamps["request_start"]) * 1000,
                    "adapter_ingest_ms": (timestamps["adapter_ingest"] - timestamps["websocket_send"]) * 1000 if timestamps["adapter_ingest"] else None,
                    "moshi_inference_ms": (timestamps["first_token"] - timestamps["moshi_inference_start"]) * 1000 if timestamps["moshi_inference_start"] else None,
                    "total_ttft_ms": first_token_time * 1000
                }
                
                self.telemetry.log("ttft_measurement", {
                    "session_id": session_id,
                    "language": language,
                    "latencies": hop_latencies,
                    "timestamps": timestamps
                })
                
                return hop_latencies["total_ttft_ms"]
                
        except asyncio.TimeoutError:
            self.telemetry.log("ttft_timeout", {
                "session_id": session_id,
                "language": language,
                "timestamps": timestamps
            })
            return None
        except Exception as e:
            self.telemetry.log("ttft_error", {
                "session_id": session_id,
                "language": language,
                "error": str(e),
                "timestamps": timestamps
            })
            return None
    
    async def run_benchmark(self):
        """Run TTFT benchmark with warmup iterations"""
        iterations = self.config['benchmarks']['ttft']['iterations']
        warmup = self.config['benchmarks']['ttft']['warmup_iterations']
        total_iterations = warmup + iterations
        
        print(f"Running TTFT Benchmark ({iterations} iterations + {warmup} warmup)...")
        print(f"Target median: <{self.target_ms}ms")
        
        languages = ["ru", "uz"]
        
        for i in range(total_iterations):
            is_warmup = i < warmup
            language = languages[i % len(languages)]
            session_id = str(uuid.uuid4())
            
            if is_warmup:
                print(f"  Warmup {i+1}/{warmup} ({language})")
            else:
                print(f"  Iteration {i-warmup+1}/{iterations} ({language})")
            
            latency = await self.measure_ttft(session_id, language)
            
            if latency is not None and not is_warmup:
                self.latencies.append(latency)
            elif latency is None:
                print(f"    Failed")
            
            await asyncio.sleep(0.1)  # Brief pause between requests
        
        # Save telemetry
        log_file = self.telemetry.save()
        print(f"  Telemetry saved to: {log_file}")
    
    def calculate_statistics(self) -> Dict:
        """Calculate TTFT statistics"""
        if not self.latencies:
            return {
                "median_ms": None,
                "mean_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "min_ms": None,
                "max_ms": None,
                "std_dev_ms": None,
                "samples": 0
            }
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return {
            "median_ms": statistics.median(sorted_latencies),
            "mean_ms": statistics.mean(sorted_latencies),
            "p50_ms": sorted_latencies[int(n * 0.5)],
            "p95_ms": sorted_latencies[int(n * 0.95)],
            "p99_ms": sorted_latencies[int(n * 0.99)],
            "min_ms": min(sorted_latencies),
            "max_ms": max(sorted_latencies),
            "std_dev_ms": statistics.stdev(sorted_latencies) if n > 1 else 0,
            "samples": n
        }
    
    def generate_report(self) -> Dict:
        """Generate benchmark report"""
        stats = self.calculate_statistics()
        
        report = {
            "test_name": "TTFT Benchmark",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config['benchmarks']['ttft'],
            "target_median_ms": self.target_ms,
            "statistics": stats,
            "status": "PASS" if stats["median_ms"] and stats["median_ms"] < self.target_ms else "FAIL",
            "summary": {
                "samples": stats["samples"],
                "median_ms": f"{stats['median_ms']:.2f}" if stats["median_ms"] else "N/A",
                "mean_ms": f"{stats['mean_ms']:.2f}" if stats["mean_ms"] else "N/A",
                "p95_ms": f"{stats['p95_ms']:.2f}" if stats["p95_ms"] else "N/A",
                "p99_ms": f"{stats['p99_ms']:.2f}" if stats["p99_ms"] else "N/A",
                "worst_case_ms": f"{stats['max_ms']:.2f}" if stats["max_ms"] else "N/A",
                "target_met": stats["median_ms"] and stats["median_ms"] < self.target_ms
            }
        }
        
        return report

async def main():
    benchmark = TTFTBenchmark()
    await benchmark.run_benchmark()
    
    report = benchmark.generate_report()
    
    # Save JSON report
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    
    json_file = os.path.join(report_dir, "ttft.json")
    with open(json_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Save CSV report
    csv_file = os.path.join(report_dir, "ttft.csv")
    with open(csv_file, 'w') as f:
        f.write("metric,value\n")
        f.write(f"median_ms,{report['statistics']['median_ms']}\n")
        f.write(f"mean_ms,{report['statistics']['mean_ms']}\n")
        f.write(f"p50_ms,{report['statistics']['p50_ms']}\n")
        f.write(f"p95_ms,{report['statistics']['p95_ms']}\n")
        f.write(f"p99_ms,{report['statistics']['p99_ms']}\n")
        f.write(f"min_ms,{report['statistics']['min_ms']}\n")
        f.write(f"max_ms,{report['statistics']['max_ms']}\n")
        f.write(f"std_dev_ms,{report['statistics']['std_dev_ms']}\n")
        f.write(f"samples,{report['statistics']['samples']}\n")
    
    # Save Markdown report
    md_file = os.path.join(report_dir, "ttft.md")
    with open(md_file, 'w') as f:
        f.write("# TTFT Benchmark Report\n\n")
        f.write(f"**Timestamp:** {report['timestamp']}\n")
        f.write(f"**Status:** {report['status']}\n")
        f.write(f"**Target Median:** <{report['target_median_ms']}ms\n\n")
        f.write("## Summary\n\n")
        for key, value in report['summary'].items():
            f.write(f"- **{key}:** {value}\n")
        f.write("\n## Statistics\n\n")
        f.write(f"```json\n{json.dumps(report['statistics'], indent=2)}\n```\n")
    
    print(f"\nReports saved:")
    print(f"  JSON: {json_file}")
    print(f"  CSV: {csv_file}")
    print(f"  Markdown: {md_file}")
    print(f"Status: {report['status']}")
    
    sys.exit(0 if report['status'] == "PASS" else 1)

if __name__ == "__main__":
    asyncio.run(main())
