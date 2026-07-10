#!/bin/bash
# Aziza Benchmark Setup and Execution Script
# Run this on aziza-worker-01 (83.126.40.53:122) in /root/aziza-build/

set -e

echo "========================================"
echo "Aziza Milestone 2 Benchmark Setup"
echo "========================================"
echo ""

# Navigate to aziza-build directory
cd /root/aziza-build

# Create benchmarks directory structure
echo "Creating directory structure..."
mkdir -p benchmarks/{scripts,data,reports,telemetry}
mkdir -p benchmarks/.github/workflows

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install pyyaml websockets psutil GPUtil --quiet || {
    echo "Warning: Some dependencies may have failed to install"
    echo "Attempting to install individually..."
    pip3 install pyyaml
    pip3 install websockets
    pip3 install psutil
    pip3 install GPUtil || echo "GPUtil may not be available on this system"
}

# Create benchmark configuration
echo "Creating benchmark configuration..."
cat > benchmarks/benchmark_config.yaml << 'EOF'
version: "1.0"
environment:
  worker_host: "aziza-worker-01"
  api_gateway_url: "http://localhost:8080"
  personaplex_url: "http://localhost:8000"
  websocket_url: "ws://localhost:8080/api/chat"
  
targets:
  ttft_median_ms: 300
  text_to_text_s: 3
  voice_to_text_s: 2
  voice_roundtrip_ms: 300
  stability_duration_min: 10
  
benchmarks:
  e2e_integration:
    enabled: true
    iterations: 10
    timeout_s: 30
    
  ttft:
    enabled: true
    iterations: 100
    warmup_iterations: 5
    
  text_to_text:
    enabled: true
    iterations: 100
    prompt_file: "data/text_prompts.json"
    
  voice_to_text:
    enabled: true
    sample_dir: "data/voice_samples"
    languages: ["ru", "uz"]
    
  voice_roundtrip:
    enabled: true
    iterations: 100
    audio_duration_ms: 2000
    
  stability:
    enabled: true
    duration_min: 10
    persona_switch_interval_s: 60
    
telemetry:
  log_dir: "telemetry"
  log_format: "json"
  log_level: "INFO"
  metrics:
    - request_id
    - session_id
    - timestamp
    - adapter_latency_ms
    - inference_latency_ms
    - streaming_latency_ms
    - total_latency_ms
    - errors
    - reconnects
    - dropped_frames
    
ci:
  fail_on_ttft_breach: true
  fail_on_text_breach: true
  fail_on_voice_breach: true
  fail_on_roundtrip_breach: true
  fail_on_integration_failure: true
  fail_on_websocket_disconnect: true
  fail_on_benchmark_crash: true
  artifact_dir: "reports"
EOF

# Make scripts executable
chmod +x benchmarks/scripts/*.sh

echo ""
echo "========================================"
echo "Setup Complete"
echo "========================================"
echo ""
echo "To run benchmarks:"
echo "  cd /root/aziza-build/benchmarks"
echo "  ./scripts/run_benchmarks.sh"
echo ""
echo "Or run individual benchmarks:"
echo "  python3 scripts/e2e_integration_test.py"
echo "  python3 scripts/ttft_benchmark.py"
echo "  python3 scripts/text_to_text_benchmark.py"
echo "  python3 scripts/voice_to_text_validation.py"
echo "  python3 scripts/voice_roundtrip_benchmark.py"
echo "  python3 scripts/stability_test.py"
echo ""
