#!/usr/bin/env python3
"""
Aziza Voice↔Voice Round-Trip Benchmark
Measures latency from mic capture to playback start (100 runs, target <300ms)
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
        log_file = os.path.join(self.log_dir, f"voice_roundtrip_{self.session_id}.json")
        with open(log_file, 'w') as f:
            json.dump(self.logs, f, indent=2)
        return log_file

class VoiceRoundtripBenchmark:
    def __init__(self, config_path: str = "benchmark_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.telemetry = TelemetryLogger(self.config['telemetry']['log_dir'])
        self.latencies = []
        self.target_ms = self.config['targets']['voice_roundtrip_ms']
        
    async def measure_roundtrip(self, audio_duration_ms: int = 2000) -> Optional[float]:
        """
        Measure voice round-trip latency (mic capture → processing → playback start)
        Returns latency in milliseconds or None if failed
        """
        ws_url = self.config['environment']['websocket_url']
        session_id = str(uuid.uuid4())
        
        # Timestamps
        timestamps = {
            "mic_capture": None,
            "audio_send": None,
            "processing_start": None,
            "playback_start": None
        }
        
        try:
            timestamps["mic_capture"] = time.time()
            
            async with websockets.connect(ws_url) as websocket:
                timestamps["audio_send"] = time.time()
                
                # Send audio for round-trip
                request = {
                    "type": "voice_roundtrip",
                    "session_id": session_id,
                    "audio_format": "wav",
                    "sample_rate": 16000,
                    "duration_ms": audio_duration_ms
                }
                
                await websocket.send(json.dumps(request))
                
                # Generate and send synthetic audio
                audio_data = self._generate_test_audio(audio_duration_ms)
                chunk_size = 4096
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i+chunk_size]
                    await websocket.send(chunk)
                
                # Signal end of audio
                await websocket.send(json.dumps({"type": "audio_end", "session_id": session_id}))
                
                # Wait for playback start signal
                playback_time = None
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "playback_start":
                        timestamps["playback_start"] = time.time()
                        playback_time = (timestamps["playback_start"] - timestamps["mic_capture"]) * 1000
                        break
                    elif data.get("type") == "processing_start":
                        timestamps["processing_start"] = time.time()
                    elif data.get("type") == "error":
                        raise Exception(f"Server error: {data.get('message')}")
                
                # Clean shutdown
                await websocket.send(json.dumps({"type": "end_session", "session_id": session_id}))
                
                # Calculate hop latencies
                hop_latencies = {
                    "audio_send_ms": (timestamps["audio_send"] - timestamps["mic_capture"]) * 1000,
                    "processing_ms": (timestamps["playback_start"] - timestamps["processing_start"]) * 1000 if timestamps["processing_start"] else None,
                    "total_roundtrip_ms": playback_time
                }
                
                self.telemetry.log("voice_roundtrip", {
                    "session_id": session_id,
                    "latencies": hop_latencies,
                    "audio_duration_ms": audio_duration_ms
                })
                
                return hop_latencies["total_roundtrip_ms"]
                
        except asyncio.TimeoutError:
            self.telemetry.log("roundtrip_timeout", {
                "session_id": session_id,
                "timestamps": timestamps
            })
            return None
        except Exception as e:
            self.telemetry.log("roundtrip_error", {
                "session_id": session_id,
                "error": str(e),
                "timestamps": timestamps
            })
            return None
    
    def _generate_test_audio(self, duration_ms: int) -> bytes:
        """Generate synthetic test audio"""
        import wave
        import io
        import math
        import struct
        
        sample_rate = 16000
        num_samples = int(sample_rate * duration_ms / 1000)
        
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            for i in range(num_samples):
                value = int(32767 * 0.3 * (1 + math.sin(2 * math.pi * 440 * i / sample_rate)))
                wav_file.writeframes(struct.pack('<h', value))
        
        return buffer.getvalue()
    
    async def run_benchmark(self):
        """Run voice round-trip benchmark"""
        iterations = self.config['benchmarks']['voice_roundtrip']['iterations']
        audio_duration = self.config['benchmarks']['voice_roundtrip']['audio_duration_ms']
        
        print(f"Running Voice↔Voice Round-Trip Benchmark ({iterations} runs)...")
        print(f"Target: <{self.target_ms}ms")
        print(f"Audio duration: {audio_duration}ms")
        
        for i in range(iterations):
            print(f"  Run {i+1}/{iterations}")
            
            latency = await self.measure_roundtrip(audio_duration)
            
            if latency is not None:
                self.latencies.append(latency)
                print(f"    {latency:.2f}ms")
            else:
                print(f"    Failed")
            
            await asyncio.sleep(0.05)
        
        # Save telemetry
        log_file = self.telemetry.save()
        print(f"  Telemetry saved to: {log_file}")
    
    def calculate_statistics(self) -> Dict:
        """Calculate round-trip statistics"""
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
    
    def generate_histogram(self) -> Dict:
        """Generate latency histogram data"""
        if not self.latencies:
            {}
        
        bins = [0, 50, 100, 150, 200, 250, 300, 350, 400, 500, 1000]
        histogram = {}
        
        for i in range(len(bins) - 1):
            bin_start = bins[i]
            bin_end = bins[i + 1]
            count = sum(1 for lat in self.latencies if bin_start <= lat < bin_end)
            histogram[f"{bin_start}-{bin_end}ms"] = count
        
        return histogram
    
    def generate_report(self) -> Dict:
        """Generate benchmark report"""
        stats = self.calculate_statistics()
        histogram = self.generate_histogram()
        
        report = {
            "test_name": "Voice↔Voice Round-Trip Benchmark",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config['benchmarks']['voice_roundtrip'],
            "target_ms": self.target_ms,
            "statistics": stats,
            "histogram": histogram,
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
    benchmark = VoiceRoundtripBenchmark()
    await benchmark.run_benchmark()
    
    report = benchmark.generate_report()
    
    # Save report
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "voice_roundtrip.md")
    
    with open(report_file, 'w') as f:
        f.write("# Voice↔Voice Round-Trip Benchmark Report\n\n")
        f.write(f"**Timestamp:** {report['timestamp']}\n")
        f.write(f"**Status:** {report['status']}\n")
        f.write(f"**Target:** <{report['target_ms']}ms\n\n")
        f.write("## Summary\n\n")
        for key, value in report['summary'].items():
            f.write(f"- **{key}:** {value}\n")
        f.write("\n## Statistics\n\n")
        f.write(f"```json\n{json.dumps(report['statistics'], indent=2)}\n```\n")
        f.write("\n## Latency Histogram\n\n")
        f.write("| Latency Range | Count |\n")
        f.write("|---------------|-------|\n")
        for range_key, count in report.get('histogram', {}).items():
            f.write(f"| {range_key} | {count} |\n")
    
    print(f"\nReport saved to: {report_file}")
    print(f"Status: {report['status']}")
    
    sys.exit(0 if report['status'] == "PASS" else 1)

if __name__ == "__main__":
    asyncio.run(main())
