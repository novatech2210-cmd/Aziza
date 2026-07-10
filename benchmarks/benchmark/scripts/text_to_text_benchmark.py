#!/usr/bin/env python3
"""
Aziza Text→Text Benchmark
Tests 100 varied prompts (factual, code, summarization, creative) with target <3s response
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
        log_file = os.path.join(self.log_dir, f"text_to_text_{self.session_id}.json")
        with open(log_file, 'w') as f:
            json.dump(self.logs, f, indent=2)
        return log_file

class TextToTextBenchmark:
    def __init__(self, config_path: str = "benchmark_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.telemetry = TelemetryLogger(self.config['telemetry']['log_dir'])
        self.latencies = []
        self.target_s = self.config['targets']['text_to_text_s']
        self.prompts = self._load_prompts()
        
    def _load_prompts(self) -> List[Dict]:
        """Load or generate test prompts"""
        prompt_file = self.config['benchmarks']['text_to_text']['prompt_file']
        
        # Check if prompt file exists
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r') as f:
                return json.load(f)
        
        # Generate default prompts
        default_prompts = [
            # Factual questions
            {"category": "factual", "text": "What is the capital of France?", "language": "en"},
            {"category": "factual", "text": "Сколько людей живет в Москве?", "language": "ru"},
            {"category": "factual", "text": "Тошкентда неча киши яшайди?", "language": "uz"},
            
            # Code questions
            {"category": "code", "text": "Write a Python function to reverse a string", "language": "en"},
            {"category": "code", "text": "Напиши функцию на Python для сортировки списка", "language": "ru"},
            
            # Summarization
            {"category": "summarization", "text": "Summarize the benefits of renewable energy in 3 sentences", "language": "en"},
            {"category": "summarization", "text": "Опиши преимущества искусственного интеллекта кратко", "language": "ru"},
            
            # Creative
            {"category": "creative", "text": "Write a short poem about technology", "language": "en"},
            {"category": "creative", "text": "Расскажи короткую историю о космосе", "language": "ru"},
        ]
        
        # Duplicate to reach 100 prompts
        while len(default_prompts) < 100:
            default_prompts.extend(default_prompts[:10])
        
        return default_prompts[:100]
    
    async def measure_text_response(self, prompt: Dict) -> Optional[float]:
        """
        Measure text response time for a single prompt
        Returns latency in seconds or None if failed
        """
        ws_url = self.config['environment']['websocket_url']
        session_id = str(uuid.uuid4())
        
        try:
            start_time = time.time()
            
            async with websockets.connect(ws_url) as websocket:
                # Send text request
                request = {
                    "type": "text_request",
                    "session_id": session_id,
                    "text": prompt["text"],
                    "language": prompt["language"],
                    "category": prompt["category"]
                }
                
                await websocket.send(json.dumps(request))
                
                # Wait for response
                response_time = None
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "text_response":
                        response_time = time.time() - start_time
                        break
                    elif data.get("type") == "error":
                        raise Exception(f"Server error: {data.get('message')}")
                
                # Clean shutdown
                await websocket.send(json.dumps({"type": "end_session", "session_id": session_id}))
                
                self.telemetry.log("text_response", {
                    "session_id": session_id,
                    "category": prompt["category"],
                    "language": prompt["language"],
                    "latency_s": response_time,
                    "prompt_length": len(prompt["text"])
                })
                
                return response_time
                
        except asyncio.TimeoutError:
            self.telemetry.log("text_timeout", {
                "session_id": session_id,
                "category": prompt["category"],
                "language": prompt["language"]
            })
            return None
        except Exception as e:
            self.telemetry.log("text_error", {
                "session_id": session_id,
                "category": prompt["category"],
                "language": prompt["language"],
                "error": str(e)
            })
            return None
    
    async def run_benchmark(self):
        """Run text-to-text benchmark"""
        iterations = self.config['benchmarks']['text_to_text']['iterations']
        
        print(f"Running Text→Text Benchmark ({iterations} prompts)...")
        print(f"Target: <{self.target_s}s")
        
        for i, prompt in enumerate(self.prompts[:iterations]):
            print(f"  Prompt {i+1}/{iterations} ({prompt['category']}, {prompt['language']})")
            
            latency = await self.measure_text_response(prompt)
            
            if latency is not None:
                self.latencies.append(latency)
                print(f"    {latency:.2f}s")
            else:
                print(f"    Failed")
            
            await asyncio.sleep(0.05)  # Brief pause between requests
        
        # Save telemetry
        log_file = self.telemetry.save()
        print(f"  Telemetry saved to: {log_file}")
    
    def calculate_statistics(self) -> Dict:
        """Calculate response time statistics"""
        if not self.latencies:
            return {
                "median_s": None,
                "mean_s": None,
                "p50_s": None,
                "p95_s": None,
                "p99_s": None,
                "min_s": None,
                "max_s": None,
                "std_dev_s": None,
                "samples": 0
            }
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return {
            "median_s": statistics.median(sorted_latencies),
            "mean_s": statistics.mean(sorted_latencies),
            "p50_s": sorted_latencies[int(n * 0.5)],
            "p95_s": sorted_latencies[int(n * 0.95)],
            "p99_s": sorted_latencies[int(n * 0.99)],
            "min_s": min(sorted_latencies),
            "max_s": max(sorted_latencies),
            "std_dev_s": statistics.stdev(sorted_latencies) if n > 1 else 0,
            "samples": n
        }
    
    def generate_report(self) -> Dict:
        """Generate benchmark report"""
        stats = self.calculate_statistics()
        
        report = {
            "test_name": "Text→Text Benchmark",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config['benchmarks']['text_to_text'],
            "target_s": self.target_s,
            "statistics": stats,
            "status": "PASS" if stats["median_s"] and stats["median_s"] < self.target_s else "FAIL",
            "summary": {
                "samples": stats["samples"],
                "median_s": f"{stats['median_s']:.2f}" if stats["median_s"] else "N/A",
                "mean_s": f"{stats['mean_s']:.2f}" if stats["mean_s"] else "N/A",
                "p95_s": f"{stats['p95_s']:.2f}" if stats["p95_s"] else "N/A",
                "p99_s": f"{stats['p99_s']:.2f}" if stats["p99_s"] else "N/A",
                "worst_case_s": f"{stats['max_s']:.2f}" if stats["max_s"] else "N/A",
                "target_met": stats["median_s"] and stats["median_s"] < self.target_s
            }
        }
        
        return report

async def main():
    benchmark = TextToTextBenchmark()
    await benchmark.run_benchmark()
    
    report = benchmark.generate_report()
    
    # Save report
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "text_to_text.md")
    
    with open(report_file, 'w') as f:
        f.write("# Text→Text Benchmark Report\n\n")
        f.write(f"**Timestamp:** {report['timestamp']}\n")
        f.write(f"**Status:** {report['status']}\n")
        f.write(f"**Target:** <{report['target_s']}s\n\n")
        f.write("## Summary\n\n")
        for key, value in report['summary'].items():
            f.write(f"- **{key}:** {value}\n")
        f.write("\n## Statistics\n\n")
        f.write(f"```json\n{json.dumps(report['statistics'], indent=2)}\n```\n")
    
    print(f"\nReport saved to: {report_file}")
    print(f"Status: {report['status']}")
    
    sys.exit(0 if report['status'] == "PASS" else 1)

if __name__ == "__main__":
    asyncio.run(main())
