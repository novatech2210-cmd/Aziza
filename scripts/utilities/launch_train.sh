#!/usr/bin/env bash
# Launch Moshi fine-tuning in background and show initial log
set -euo pipefail
cd /root/aziza-build
source venv/bin/activate
pkill -9 -f finetune_moshi 2>/dev/null || true
sleep 1
CUDA_LAUNCH_BLOCKING=1 nohup python3 finetune_moshi.py \
  --output_dir ./aziza-multilingual-adapter \
  --data_dir ./backend/fine-tuning/data \
  --lang ru \
  --epochs 1 \
  > /tmp/moshi_train.log 2>&1 &
echo "TRAINING_PID: $!"
