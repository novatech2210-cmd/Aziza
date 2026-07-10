#!/bin/bash
set -euo pipefail

source /root/aziza-build/.env 2>/dev/null || true
source /root/aziza-build/venv/bin/activate

: "${HF_TOKEN:?HF_TOKEN must be set in .env or environment}"
export HF_TOKEN
export HUGGINGFACE_TOKEN="$HF_TOKEN"
export TRANSFORMERS_CACHE=/root/.cache/huggingface
export HF_HOME=/root/.cache/huggingface

mkdir -p /root/aziza-build/logs
LOG="/root/aziza-build/logs/eval_russian_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=============================="
echo "[START] eval_russian.py — Gate Suite"
echo "Date:    $(date)"
echo "GPU:     $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"
echo "Adapter: /root/aziza-build/training/lora/ru_all"
echo "Model:   Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
echo "=============================="

python3 /root/aziza-build/eval_russian.py \
  --adapter /root/aziza-build/training/lora/ru_all \
  --model_id Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24 \
  --pass_rate_threshold 0.8 \
  --cyrillic_threshold 0.8 \
  --ttft_target_ms 3000

EXIT_CODE=$?
echo "=============================="
echo "[DONE] eval exit=$EXIT_CODE at $(date)"
echo "=============================="
exit $EXIT_CODE
