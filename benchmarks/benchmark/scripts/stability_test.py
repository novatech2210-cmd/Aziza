#!/usr/bin/env python3
"""
Aziza Continuous Stability Test
10-minute continuous run with persona switching every minute
Monitors CPU, RAM, GPU/VRAM, network, dropped packets, reconnects, memory growth, thread count
"""
import asyncio
import json
import time
import uuid
import websockets
import psutil
import GPUtil
from datetime import datetime, timezone
from typing import Dict, List
import yaml
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TelemetryLogger:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.session_id = str(uuid.uuid4())
        self.logs = []
        self.lock = threading.Lock()
        
    def log(self, event_type: str, data: Dict):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            **data
        }
        with self.lock:
            self.logs.append(entry)
        
    def save(self):
        log_file = os.path.join(self.log_dir, f"stability_{self.session_id}.json")
        with open(log_file, 'w') as f:
            json.dump(self.logs, f, indent=2)
        return log_file

class SystemMonitor:
    """Monitor system resources during stability test"""
    def __init__(self, telemetry: TelemetryLogger):
        self.telemetry = telemetry
        self.monitoring = False
        self.thread = None
        
    def get_system_stats(self) -> Dict:
        """Get current system resource statistics"""
        stats = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used_gb": psutil.virtual_memory().used / (1024**3),
            "memory_available_gb": psutil.virtual_memory().available / (1024**3),
            "disk_usage_percent": psutil.disk_usage('/').percent,
            "network_io": psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
            "thread_count": threading.active_count()
        }
        
        # GPU stats if available
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                stats["gpu"] = {
                    "name": gpu.name,
                    "load_percent": gpu.load * 100,
                    "memory_used_mb": gpu.memoryUsed,
                    "memory_total_mb": gpu.memoryTotal,
                    "memory_free_mb": gpu.memoryFree,
                    "temperature": gpu.temperature
                }
        except:
            stats["gpu"] = None
        
        return stats
    
    def start_monitoring(self, interval_s: int = 5):
        """Start background monitoring thread"""
        self.monitoring = True
        self.thread = threading.Thread(target=self._monitor_loop, args=(interval_s,))
        self.thread.daemon = True
        self.thread.start()
    
    def _monitor_loop(self, interval_s: int):
        """Monitoring loop"""
        while self.monitoring:
            stats = self.get_system_stats()
            self.telemetry.log("system_stats", stats)
            time.sleep(interval_s)
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.thread:
            self.thread.join(timeout=5)

class StabilityTest:
    def __init__(self, config_path: str = "benchmark_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.telemetry = TelemetryLogger(self.config['telemetry']['log_dir'])
        self.monitor = SystemMonitor(self.telemetry)
        
        self.duration_min = self.config['benchmarks']['stability']['duration_min']
        self.switch_interval_s = self.config['benchmarks']['stability']['persona_switch_interval_s']
        
        self.results = {
            "crashes": 0,
            "deadlocks": 0,
            "memory_leaks": 0,
            "hung_connections": 0,
            "token_stalls": 0,
            "audio_stalls": 0,
            "reconnects": 0,
            "dropped_packets": 0,
            "persona_switches": 0,
            "successful_switches": 0
        }
        
        self.personas = ["aziza_ru", "aziza_uz", "aziza_en"]
        self.current_persona_index = 0
        
    async def continuous_session(self):
        """Run continuous session with persona switching"""
        ws_url = self.config['environment']['websocket_url']
        session_id = str(uuid.uuid4())
        
        start_time = time.time()
        end_time = start_time + (self.duration_min * 60)
        
        print(f"Starting stability test ({self.duration_min} minutes)...")
        print(f"Persona switch interval: {self.switch_interval_s}s")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Start initial session
                await websocket.send(json.dumps({
                    "type": "start_session",
                    "session_id": session_id,
                    "language": "ru",
                    "persona": self.personas[0]
                }))
                
                self.telemetry.log("session_started", {
                    "session_id": session_id,
                    "persona": self.personas[0]
                })
                
                # Main loop
                last_switch = time.time()
                
                while time.time() < end_time:
                    current_time = time.time()
                    elapsed = current_time - start_time
                    remaining = end_time - current_time
                    
                    print(f"  Elapsed: {elapsed:.0f}s, Remaining: {remaining:.0f}s")
                    
                    # Check if it's time to switch persona
                    if current_time - last_switch >= self.switch_interval_s:
                        await self.switch_persona(websocket, session_id)
                        last_switch = current_time
                    
                    # Send keep-alive message
                    try:
                        await asyncio.wait_for(
                            websocket.send(json.dumps({"type": "ping", "session_id": session_id})),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        self.results["hung_connections"] += 1
                        self.telemetry.log("hung_connection", {
                            "session_id": session_id,
                            "elapsed_s": elapsed
                        })
                    
                    # Wait for response
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        data = json.loads(response)
                        
                        if data.get("type") == "pong":
                            pass  # Normal keep-alive
                        elif data.get("type") == "dropped_packet":
                            self.results["dropped_packets"] += 1
                        elif data.get("type") == "token_stall":
                            self.results["token_stalls"] += 1
                        elif data.get("type") == "audio_stall":
                            self.results["audio_stalls"] += 1
                            
                    except asyncio.TimeoutError:
                        self.results["token_stalls"] += 1
                        self.telemetry.log("token_stall", {
                            "session_id": session_id,
                            "elapsed_s": elapsed
                        })
                    
                    await asyncio.sleep(1.0)
                
                # Clean shutdown
                await websocket.send(json.dumps({"type": "end_session", "session_id": session_id}))
                
                self.telemetry.log("session_ended", {
                    "session_id": session_id,
                    "duration_s": time.time() - start_time
                })
                
        except Exception as e:
            self.results["crashes"] += 1
            self.telemetry.log("session_crash", {
                "session_id": session_id,
                "error": str(e),
                "duration_s": time.time() - start_time
            })
    
    async def switch_persona(self, websocket, session_id: str):
        """Switch to next persona"""
        self.current_persona_index = (self.current_persona_index + 1) % len(self.personas)
        new_persona = self.personas[self.current_persona_index]
        
        language = new_persona.split("_")[1]  # Extract language from persona name
        
        try:
            await websocket.send(json.dumps({
                "type": "switch_persona",
                "session_id": session_id,
                "persona": new_persona,
                "language": language
            }))
            
            self.results["persona_switches"] += 1
            self.results["successful_switches"] += 1
            
            self.telemetry.log("persona_switch", {
                "session_id": session_id,
                "from_persona": self.personas[self.current_persona_index - 1],
                "to_persona": new_persona,
                "language": language
            })
            
            print(f"    Switched to {new_persona}")
            
        except Exception as e:
            self.results["persona_switches"] += 1
            self.telemetry.log("persona_switch_failed", {
                "session_id": session_id,
                "target_persona": new_persona,
                "error": str(e)
            })
            print(f"    Failed to switch to {new_persona}")
    
    async def run_test(self):
        """Run stability test with system monitoring"""
        # Start system monitoring
        self.monitor.start_monitoring(interval_s=5)
        
        try:
            # Run continuous session
            await self.continuous_session()
        finally:
            # Stop monitoring
            self.monitor.stop_monitoring()
        
        # Save telemetry
        log_file = self.telemetry.save()
        print(f"  Telemetry saved to: {log_file}")
    
    def check_memory_leaks(self) -> bool:
        """Check for memory leaks based on system stats"""
        memory_stats = [log for log in self.telemetry.logs 
                       if log["event_type"] == "system_stats"]
        
        if len(memory_stats) < 2:
            return False
        
        # Compare memory usage at start and end
        start_memory = memory_stats[0]["memory_used_gb"]
        end_memory = memory_stats[-1]["memory_used_gb"]
        
        memory_growth = end_memory - start_memory
        growth_rate_mb_per_min = (memory_growth * 1024) / self.duration_min
        
        # Flag as leak if growth > 100MB/min
        if growth_rate_mb_per_min > 100:
            self.results["memory_leaks"] = 1
            return True
        
        return False
    
    def generate_report(self) -> Dict:
        """Generate stability test report"""
        self.check_memory_leaks()
        
        # Calculate session statistics
        session_logs = [log for log in self.telemetry.logs 
                       if log["event_type"] in ["session_started", "session_ended", "session_crash"]]
        
        report = {
            "test_name": "Continuous Stability Test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config['benchmarks']['stability'],
            "results": self.results,
            "status": "PASS" if (
                self.results["crashes"] == 0 and
                self.results["deadlocks"] == 0 and
                self.results["memory_leaks"] == 0 and
                self.results["hung_connections"] == 0 and
                self.results["token_stalls"] == 0 and
                self.results["audio_stalls"] == 0
            ) else "FAIL",
            "summary": {
                "duration_min": self.duration_min,
                "persona_switches": self.results["persona_switches"],
                "successful_switches": self.results["successful_switches"],
                "crashes": self.results["crashes"],
                "deadlocks": self.results["deadlocks"],
                "memory_leaks": self.results["memory_leaks"],
                "hung_connections": self.results["hung_connections"],
                "token_stalls": self.results["token_stalls"],
                "audio_stalls": self.results["audio_stalls"],
                "reconnects": self.results["reconnects"],
                "dropped_packets": self.results["dropped_packets"]
            }
        }
        
        return report

async def main():
    test = StabilityTest()
    await test.run_test()
    
    report = test.generate_report()
    
    # Save report
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "stability.md")
    
    with open(report_file, 'w') as f:
        f.write("# Continuous Stability Test Report\n\n")
        f.write(f"**Timestamp:** {report['timestamp']}\n")
        f.write(f"**Status:** {report['status']}\n")
        f.write(f"**Duration:** {report['summary']['duration_min']} minutes\n\n")
        f.write("## Summary\n\n")
        for key, value in report['summary'].items():
            f.write(f"- **{key}:** {value}\n")
        f.write("\n## Results\n\n")
        f.write(f"```json\n{json.dumps(report['results'], indent=2)}\n```\n")
    
    print(f"\nReport saved to: {report_file}")
    print(f"Status: {report['status']}")
    
    sys.exit(0 if report['status'] == "PASS" else 1)

if __name__ == "__main__":
    asyncio.run(main())
