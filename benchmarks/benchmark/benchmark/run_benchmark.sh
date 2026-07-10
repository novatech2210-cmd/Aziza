#!/bin/bash
set -e

echo "=========================================="
echo " PersonaPlex Server-Side Concurrency Test "
echo "=========================================="
echo "Target Sessions: 8"
echo "Hardware: H100_SXM / L40S Server"
echo ""

# 1. Start Redis if not running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "[!] Redis is not running. Attempting to start..."
    sudo apt-get update && sudo apt-get install -y redis-server
    sudo service redis-server start
fi

# 2. Setup python environment
echo "[*] Setting up Python environment..."
cd /root/AZIZA-BUILD
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install redis numpy pynvml

# 3. Start Moshi Engine
echo "[*] Starting Moshi Inference Engine..."
pkill -f moshi_service.py || true
cd /root/AZIZA-BUILD/moshi-runtime
export ENABLE_FP8=1
export REDIS_URL='redis://localhost:6379'
nohup python moshi_service.py > moshi_service.log 2>&1 &
MOSHI_PID=$!
cd /root/AZIZA-BUILD/benchmark

# Wait for initialization
echo "[*] Waiting 15 seconds for models to load into VRAM..."
sleep 15

# 4. Run Benchmark
echo "[*] Running Benchmark (8 Sessions)..."
python benchmark.py --sessions 8

echo "[*] Benchmark complete."

# 5. Cleanup
echo "[*] Stopping Moshi Engine..."
kill $MOSHI_PID

# 6. Package results
echo "[*] Packaging results into benchmark_results.tar.gz..."
tar -czvf benchmark_results.tar.gz results/ ../moshi-runtime/moshi_service.log

echo "Done! You can download benchmark_results.tar.gz to verify the metrics."
