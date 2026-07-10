# Aziza Benchmark Deployment Guide

## Remote Server Setup

The benchmark suite must be run on `aziza-worker-01` (83.126.40.53:122) where the Aziza pipeline is deployed.

## Quick Start

### 1. SSH to Server
```bash
ssh -p 122 pers@83.126.40.53
# Password: aziza1234
sudo su
# Password: aziza1234
cd /root/aziza-build
```

### 2. Transfer Benchmark Code
From your local machine:
```bash
scp -P 122 -r /home/kali/Desktop/AZIZA-BUILD/benchmarks pers@83.126.40.53:/root/aziza-build/
```

### 3. Run Setup Script
On the remote server:
```bash
cd /root/aziza-build/benchmarks
chmod +x setup_and_run.sh
./setup_and_run.sh
```

### 4. Run Benchmarks
```bash
cd /root/aziza-build/benchmarks
./scripts/run_benchmarks.sh
```

## Manual Setup (Alternative)

If the setup script fails, perform these steps manually:

### Install Dependencies
```bash
pip3 install pyyaml websockets psutil GPUtil
```

### Create Directory Structure
```bash
cd /root/aziza-build
mkdir -p benchmarks/{scripts,data,reports,telemetry}
mkdir -p benchmarks/.github/workflows
```

### Copy Files
Copy all files from the local `benchmarks/` directory to `/root/aziza-build/benchmarks/` on the server.

### Make Scripts Executable
```bash
chmod +x benchmarks/scripts/*.sh
```

## Configuration

Edit `benchmarks/benchmark_config.yaml` to match your environment:

```yaml
environment:
  api_gateway_url: "http://localhost:8080"  # NestJS gateway
  personaplex_url: "http://localhost:8000"  # PersonaPlex backend
  websocket_url: "ws://localhost:8080/ws"  # WebSocket endpoint
```

## Running Individual Benchmarks

### E2E Integration Test
```bash
cd /root/aziza-build/benchmarks
python3 scripts/e2e_integration_test.py
```

### TTFT Benchmark
```bash
python3 scripts/ttft_benchmark.py
```

### Text→Text Benchmark
```bash
python3 scripts/text_to_text_benchmark.py
```

### Voice→Text Validation
```bash
python3 scripts/voice_to_text_validation.py
```

### Voice↔Voice Round-Trip
```bash
python3 scripts/voice_roundtrip_benchmark.py
```

### Stability Test
```bash
python3 scripts/stability_test.py
```

## Collecting Results

After running benchmarks, collect the reports:

```bash
# From local machine
scp -P 122 -r pers@83.126.40.53:/root/aziza-build/benchmarks/reports /home/kali/Desktop/AZIZA-BUILD/benchmarks/
scp -P 122 -r pers@83.126.40.53:/root/aziza-build/benchmarks/telemetry /home/kali/Desktop/AZIZA-BUILD/benchmarks/
```

## Troubleshooting

### WebSocket Connection Failures
- Verify services are running: `systemctl status personaplex moshi-worker`
- Check ports: `netstat -tlnp | grep -E '8000|8080'`
- Test connectivity: `curl http://localhost:8080/health`

### GPU Not Available
- Check GPU: `nvidia-smi`
- Verify CUDA: `python3 -c "import torch; print(torch.cuda.is_available())"`

### Missing Dependencies
```bash
pip3 install --upgrade pip
pip3 install pyyaml websockets psutil
# GPUtil is optional - benchmarks will work without it
```

### Permission Issues
```bash
chmod +x /root/aziza-build/benchmarks/scripts/*.sh
chmod -R 755 /root/aziza-build/benchmarks
```

## Service Status Check

Before running benchmarks, verify all services are operational:

```bash
# Check PersonaPlex
curl http://localhost:8000/health

# Check API Gateway
curl http://localhost:8080/health

# Check Moshi Worker
curl http://localhost:9000/health

# Check Redis
redis-cli ping

# Check GPU
nvidia-smi
```

## Expected Output

After successful completion, you'll find:

- `reports/e2e_integration.md` - E2E test results
- `reports/ttft.json` - TTFT raw data
- `reports/ttft.csv` - TTFT CSV export
- `reports/ttft.md` - TTFT summary
- `reports/text_to_text.md` - Text→Text results
- `reports/voice_to_text.md` - Voice→Text validation
- `reports/voice_roundtrip.md` - Round-trip benchmark
- `reports/stability.md` - Stability test results
- `reports/final_report.md` - Overall summary

Telemetry logs in `telemetry/` directory.

## Success Criteria

All benchmarks must pass for Milestone 2 completion:

- ✓ E2E integration test passes, zero critical failures
- ✓ TTFT median <300ms
- ✓ Text→Text <3s
- ✓ Voice→Text <2s
- ✓ Voice↔Voice round-trip <300ms
- ✓ 10-minute continuous run with no crashes/deadlocks/leaks/stalls
- ✓ All .md/.json/.csv reports generated
- ✓ Telemetry/logs available for every run
