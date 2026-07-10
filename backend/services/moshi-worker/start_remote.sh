#!/bin/bash
pkill -f moshi_service.py 2>/dev/null
sleep 1
cd /workspace/moshi-worker
source venv/bin/activate

export WORKER_ID=worker_0
export HEALTH_PORT=8001
export REDIS_URL=redis://127.0.0.1:16379
export CUDA_VISIBLE_DEVICES=0
export HF_HOME=/workspace/.hf_home
export HUGGINGFACE_HUB_CACHE=/workspace/.hf_home/hub
export AZIZA_ADAPTER_PATH=""

nohup python3 moshi_service.py > /tmp/moshi_worker.log 2>&1 &
echo $! > /tmp/moshi_worker.pid
echo "Worker started with PID: $(cat /tmp/moshi_worker.pid)"
sleep 10
echo "=== Health check ==="
curl -s http://127.0.0.1:8001/health 2>/dev/null || echo "Still loading..."
tail -10 /tmp/moshi_worker.log
