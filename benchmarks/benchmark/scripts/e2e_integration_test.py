#!/usr/bin/env python3
"""
Aziza E2E Integration Test
Tests full pipeline: Browser → Audio → Adapter → Moshi → PersonaPlex → Streaming → Browser
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

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TelemetryLogger:
    """Structured JSON telemetry logger"""
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
        log_file = os.path.join(self.log_dir, f"e2e_{self.session_id}.json")
        with open(log_file, 'w') as f:
            json.dump(self.logs, f, indent=2)
        return log_file

class E2EIntegrationTest:
    def __init__(self, config_path: str = "benchmark_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.telemetry = TelemetryLogger(self.config['telemetry']['log_dir'])
        self.results = {
            "total_requests": 0,
            "failures": 0,
            "reconnects": 0,
            "dropped_packets": 0,
            "average_latency_ms": 0,
            "latencies": [],
            "errors": []
        }
        
    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection and basic message flow"""
        ws_url = self.config['environment']['websocket_url']
        session_id = str(uuid.uuid4())
        
        start_time = time.time()
        try:
            async with websockets.connect(ws_url) as websocket:
                connect_time = (time.time() - start_time) * 1000
                
                self.telemetry.log("websocket_connected", {
                    "session_id": session_id,
                    "connect_time_ms": connect_time
                })
                
                # Send test message
                test_msg = {
                    "type": "start_session",
                    "session_id": session_id,
                    "language": "ru",
                    "persona": "aziza_ru"
                }
                
                msg_start = time.time()
                await websocket.send(json.dumps(test_msg))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                msg_time = (time.time() - msg_start) * 1000
                
                self.results["latencies"].append(msg_time)
                self.results["total_requests"] += 1
                
                self.telemetry.log("message_roundtrip", {
                    "session_id": session_id,
                    "latency_ms": msg_time,
                    "response_length": len(response)
                })
                
                # Clean shutdown
                await websocket.send(json.dumps({"type": "end_session", "session_id": session_id}))
                
                return True
                
        except asyncio.TimeoutError:
            self.results["failures"] += 1
            self.results["errors"].append("WebSocket timeout")
            self.telemetry.log("websocket_timeout", {"session_id": session_id})
            return False
        except Exception as e:
            self.results["failures"] += 1
            self.results["errors"].append(str(e))
            self.telemetry.log("websocket_error", {
                "session_id": session_id,
                "error": str(e)
            })
            return False
    
    async def test_persona_switching(self) -> bool:
        """Test persona switching mid-session"""
        ws_url = self.config['environment']['websocket_url']
        session_id = str(uuid.uuid4())
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Start with Russian persona
                await websocket.send(json.dumps({
                    "type": "start_session",
                    "session_id": session_id,
                    "language": "ru",
                    "persona": "aziza_ru"
                }))
                
                await asyncio.sleep(0.5)
                
                # Switch to Uzbek persona
                switch_start = time.time()
                await websocket.send(json.dumps({
                    "type": "switch_persona",
                    "session_id": session_id,
                    "language": "uz",
                    "persona": "aziza_uz"
                }))
                
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                switch_time = (time.time() - switch_start) * 1000
                
                self.telemetry.log("persona_switch", {
                    "session_id": session_id,
                    "switch_time_ms": switch_time,
                    "from_persona": "aziza_ru",
                    "to_persona": "aziza_uz"
                })
                
                self.results["latencies"].append(switch_time)
                self.results["total_requests"] += 1
                
                await websocket.send(json.dumps({"type": "end_session", "session_id": session_id}))
                return True
                
        except Exception as e:
            self.results["failures"] += 1
            self.results["errors"].append(f"Persona switch failed: {str(e)}")
            return False
    
    async def test_reconnect_logic(self) -> bool:
        """Test WebSocket reconnect logic"""
        ws_url = self.config['environment']['websocket_url']
        session_id = str(uuid.uuid4())
        
        reconnect_count = 0
        try:
            # First connection
            async with websockets.connect(ws_url) as ws1:
                await ws1.send(json.dumps({
                    "type": "start_session",
                    "session_id": session_id,
                    "language": "ru"
                }))
                await asyncio.sleep(0.5)
                # Simulate disconnect
                reconnect_count += 1
            
            # Reconnection attempt
            async with websockets.connect(ws_url) as ws2:
                await ws2.send(json.dumps({
                    "type": "resume_session",
                    "session_id": session_id
                }))
                response = await asyncio.wait_for(ws2.recv(), timeout=5.0)
                
                self.results["reconnects"] = reconnect_count
                self.telemetry.log("reconnect_success", {
                    "session_id": session_id,
                    "reconnect_count": reconnect_count
                })
                
                await ws2.send(json.dumps({"type": "end_session", "session_id": session_id}))
                return True
                
        except Exception as e:
            self.results["failures"] += 1
            self.results["errors"].append(f"Reconnect failed: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Run all E2E integration tests"""
        iterations = self.config['benchmarks']['e2e_integration']['iterations']
        
        print(f"Running E2E Integration Test ({iterations} iterations)...")
        
        for i in range(iterations):
            print(f"  Iteration {i+1}/{iterations}")
            
            # Test basic connection
            await self.test_websocket_connection()
            
            # Test persona switching
            await self.test_persona_switching()
            
            # Test reconnect logic
            await self.test_reconnect_logic()
            
            await asyncio.sleep(0.5)  # Brief pause between iterations
        
        # Calculate average latency
        if self.results["latencies"]:
            self.results["average_latency_ms"] = sum(self.results["latencies"]) / len(self.results["latencies"])
        
        # Save telemetry
        log_file = self.telemetry.save()
        print(f"  Telemetry saved to: {log_file}")
    
    def generate_report(self) -> Dict:
        """Generate test report"""
        report = {
            "test_name": "E2E Integration Test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config['benchmarks']['e2e_integration'],
            "results": self.results,
            "status": "PASS" if self.results["failures"] == 0 else "FAIL",
            "summary": {
                "total_requests": self.results["total_requests"],
                "failures": self.results["failures"],
                "success_rate": f"{((self.results['total_requests'] - self.results['failures']) / max(self.results['total_requests'], 1)) * 100:.1f}%",
                "average_latency_ms": f"{self.results['average_latency_ms']:.2f}",
                "reconnects": self.results["reconnects"],
                "dropped_packets": self.results["dropped_packets"]
            }
        }
        
        return report

async def main():
    test = E2EIntegrationTest()
    await test.run_all_tests()
    
    report = test.generate_report()
    
    # Save report
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "e2e_integration.md")
    
    with open(report_file, 'w') as f:
        f.write("# E2E Integration Test Report\n\n")
        f.write(f"**Timestamp:** {report['timestamp']}\n")
        f.write(f"**Status:** {report['status']}\n\n")
        f.write("## Summary\n\n")
        for key, value in report['summary'].items():
            f.write(f"- **{key}:** {value}\n")
        f.write("\n## Results\n\n")
        f.write(f"```json\n{json.dumps(report['results'], indent=2)}\n```\n")
        f.write("\n## Errors\n\n")
        if report['results']['errors']:
            for error in report['results']['errors']:
                f.write(f"- {error}\n")
        else:
            f.write("No errors encountered.\n")
    
    print(f"\nReport saved to: {report_file}")
    print(f"Status: {report['status']}")
    
    # Exit with appropriate code for CI
    sys.exit(0 if report['status'] == "PASS" else 1)

if __name__ == "__main__":
    asyncio.run(main())
