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
LOG="/root/aziza-build/logs/train_russian_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=============================="
echo "[START] Russian QLoRA training"
echo "Date: $(date)"
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"
echo "Base: Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
echo "Dataset: /root/aziza-build/russian_combined.jsonl"
echo "TensorBoard: $(python3 -c 'import tensorboard; print(tensorboard.__version__)' 2>/dev/null)"
echo "=============================="

python3 /root/aziza-build/train_russian.py \
  --register all \
  --language ru \
  --dataset_path /root/aziza-build/russian_combined.jsonl \
  --output_base /root/aziza-build/adapters \
  --model_id Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24 \
  --batch_size 4 \
  --grad_accum 4 \
  --max_seq_len 512 \
  --epochs 3

EXIT_CODE=$?
echo "=============================="
echo "[DONE] exit=$EXIT_CODE at $(date)"
echo "=============================="
exit $EXIT_CODE
