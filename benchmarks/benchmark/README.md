# Aziza Milestone 2 Benchmark Suite

Comprehensive validation and benchmarking suite for the Aziza AI Assistant pipeline.

## Overview

This benchmark suite validates the complete Aziza pipeline:
```
Browser → Realtime Audio → Adapter → Moshi → PersonaPlex → Streaming Response → Browser
```

## Benchmarks

### 1. E2E Integration Test
Tests full pipeline integration including:
- WebSocket connection stability
- Adapter ingestion
- Moshi frame streaming
- PersonaPlex context/persona loading
- Token streaming
- Audio streamback
- Browser receipt
- WebSocket reconnect logic
- Clean shutdown

**Target:** Zero critical failures

### 2. TTFT Benchmark
Measures Time-To-First-Token latency across all pipeline hops.

**Configuration:**
- 100 iterations
- 5 warmup iterations
- Target median: <300ms

**Outputs:** `ttft.json`, `ttft.csv`, `ttft.md`

### 3. Text→Text Benchmark
Tests 100 varied prompts across categories:
- Factual questions
- Code generation
- Summarization
- Creative writing

**Target:** Full response <3s

**Output:** `text_to_text.md`

### 4. Voice→Text Validation
Tests prerecorded voice samples across:
- Russian and Uzbek ASR paths
- Various voices and accents
- Different speeds and noise levels

**Target:** <2s to final transcript

**Metrics:** WER, latency, dropped chunks

**Output:** `voice_to_text.md`

### 5. Voice↔Voice Round-Trip Benchmark
Measures latency from mic capture to playback start.

**Configuration:**
- 100 runs
- 2-second audio samples
- Target: <300ms

**Output:** `voice_roundtrip.md` with latency histogram

### 6. Continuous Stability Test
10-minute continuous run with:
- Persona switching every minute
- Ongoing memory/history updates
- System resource monitoring

**Monitors:**
- CPU, RAM, GPU/VRAM
- Network I/O
- Dropped packets
- Reconnects
- Memory growth
- Thread count
- Token/audio stalls

**Target:** No crashes, deadlocks, leaks, or stalls

**Output:** `stability.md`

## Installation

```bash
# Install Python dependencies
pip install pyyaml websockets psutil GPUtil

# Make scripts executable
chmod +x scripts/*.sh
```

## Usage

### Run All Benchmarks

```bash
cd benchmarks
./scripts/run_benchmarks.sh
```

### Run Individual Benchmarks

```bash
# E2E Integration Test
python3 scripts/e2e_integration_test.py

# TTFT Benchmark
python3 scripts/ttft_benchmark.py

# Text→Text Benchmark
python3 scripts/text_to_text_benchmark.py

# Voice→Text Validation
python3 scripts/voice_to_text_validation.py

# Voice↔Voice Round-Trip
python3 scripts/voice_roundtrip_benchmark.py

# Stability Test
python3 scripts/stability_test.py
```

### Configuration

Edit `benchmark_config.yaml` to customize:
- Endpoint URLs
- Target thresholds
- Iteration counts
- Timeout values
- Telemetry settings

## Outputs

All reports are generated in the `reports/` directory:
- `e2e_integration.md` - E2E test results
- `ttft.json` - TTFT raw data
- `ttft.csv` - TTFT CSV export
- `ttft.md` - TTFT summary
- `text_to_text.md` - Text→Text results
- `voice_to_text.md` - Voice→Text validation
- `voice_roundtrip.md` - Round-trip benchmark
- `stability.md` - Stability test results
- `final_report.md` - Overall summary with PASS/FAIL status

Telemetry logs are stored in `telemetry/` directory as JSON files.

## CI Integration

The benchmark suite is integrated into GitHub Actions via `.github/workflows/benchmarks.yml`.

**CI Gates:**
- Fails if TTFT >300ms
- Fails if Text→Text >3s
- Fails if Voice→Text >2s
- Fails if Voice↔Voice >300ms
- Fails on any integration failure
- Fails on WebSocket disconnect
- Fails on benchmark crash

**Artifacts:**
- Benchmark reports (30-day retention)
- Telemetry logs (30-day retention)
- PR comments with results

## Success Criteria

All benchmarks must pass for Milestone 2 completion:

- [x] E2E integration test passes, zero critical failures
- [x] TTFT median <300ms
- [x] Text→Text <3s
- [x] Voice→Text <2s
- [x] Voice↔Voice round-trip <300ms
- [x] 10-minute continuous run with no crashes/deadlocks/leaks/stalls
- [x] All .md/.json/.csv reports generated
- [x] Benchmarks enforced in CI
- [x] Telemetry/logs available for every run

## Troubleshooting

### WebSocket Connection Failures
- Verify API Gateway is running on port 8080
- Check firewall rules
- Ensure WebSocket endpoint is accessible

### GPU Not Available
- Verify GPU driver installation: `nvidia-smi`
- Check CUDA availability in Python
- Ensure Moshi worker is running

### PersonaPlex Connection Errors
- Verify PersonaPlex service on port 8000
- Check Redis connection
- Ensure MongoDB is accessible (if used)

### Timeout Errors
- Increase timeout values in `benchmark_config.yaml`
- Check system load and resource availability
- Verify network latency to endpoints

## Architecture Notes

This benchmark suite treats all pipeline components as fixed and operational:
- vLLM endpoints for Russian/Uzbek
- NestJS gateway
- PersonaPlex/Moshi V2V

No architectural changes or refactors are made unless strictly required to make a test pass.

## License

Part of the Aziza AI Platform project.
