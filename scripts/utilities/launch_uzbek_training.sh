#!/bin/bash
# launch_uzbek_training.sh
# Launches Uzbek Cyrillic then Uzbek Latin QLoRA training sequentially
# Mirrors launch_train_russian.sh pattern
set -euo pipefail

source /root/aziza-build/.env 2>/dev/null || true
source /root/aziza-build/venv/bin/activate

: "${HF_TOKEN:?HF_TOKEN must be set in .env or environment}"
export HF_TOKEN
export HUGGINGFACE_TOKEN="$HF_TOKEN"
export TRANSFORMERS_CACHE=/root/.cache/huggingface
export HF_HOME=/root/.cache/huggingface

mkdir -p /root/aziza-build/logs

# ── Phase 1: Uzbek Cyrillic ──────────────────────────────────────────────────
LOG_CYR="/root/aziza-build/logs/train_uz_cyrillic_$(date +%Y%m%d_%H%M%S).log"
echo "=============================="
echo "[START] Uzbek Cyrillic QLoRA"
echo "Date: $(date)"
echo "GPU:  $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"
echo "Log:  $LOG_CYR"
echo "=============================="

python3 /root/aziza-build/train_uzbek_cyrillic_hf.py 2>&1 | tee "$LOG_CYR"
EXIT_CYR=${PIPESTATUS[0]}
echo "=============================="
echo "[DONE] uz_cyrillic exit=$EXIT_CYR at $(date)"
echo "=============================="

if [ $EXIT_CYR -ne 0 ]; then
  echo "[ERROR] Cyrillic training failed — skipping Latin phase." >&2
  exit $EXIT_CYR
fi

# ── Phase 2: Uzbek Latin ─────────────────────────────────────────────────────
LOG_LAT="/root/aziza-build/logs/train_uz_latin_$(date +%Y%m%d_%H%M%S).log"
echo "=============================="
echo "[START] Uzbek Latin QLoRA"
echo "Date: $(date)"
echo "GPU:  $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"
echo "Log:  $LOG_LAT"
echo "=============================="

python3 /root/aziza-build/train_uzbek_latin_hf.py 2>&1 | tee "$LOG_LAT"
EXIT_LAT=${PIPESTATUS[0]}
echo "=============================="
echo "[DONE] uz_latin exit=$EXIT_LAT at $(date)"
echo "=============================="

exit $EXIT_LAT
