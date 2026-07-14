#!/bin/bash
# Train Moshi LoRA adapter for Uzbek language
# Requirements:
#   - A6000 GPU with 24GB VRAM
#   - PyTorch 2.0+
#   - PEFT, transformers, datasets, sentencepiece

set -e
cd /root/aziza-build

source /root/aziza-build/venv312/bin/activate

export CUDA_VISIBLE_DEVICES=0
export PYTHONPATH=/root/aziza-build/backend:/root/aziza-build/backend/services

echo "=== Starting Moshi Uzbek LoRA Training ==="
echo "Date: $(date)"
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"

# Create output directories
mkdir -p /root/aziza-build/training/lora/adapters/moshi_uz_v1
mkdir -p /root/aziza-build/training/logs/moshi_uz_lora

# Training parameters
BASE_MODEL="kyutai/moshika-pytorch-bf16"
DATASET="/root/aziza-build/training/datasets/aziza-uzbek.jsonl"
OUTPUT_DIR="/root/aziza-build/training/lora/adapters/moshi_uz_v1"
LOGGING_DIR="/root/aziza-build/training/logs/moshi_uz_lora"

# LoRA configuration
RANK=16
ALPHA=32
DROPOUT=0.05
LR=1e-4
BATCH_SIZE=4
GRAD_ACCUM=8
MAX_STEPS=1000
WARMUP=100

# Target modules for Moshi architecture
TARGET_MODULES="transformer.layers.{}.self_attn.in_projs.0,transformer.layers.{}.self_attn.out_projs.0,transformer.layers.{}.gating.linear_in,transformer.layers.{}.gating.linear_out,depformer.layers.{}.self_attn.in_projs.{},depformer.layers.{}.self_attn.out_projs.{},depformer.layers.{}.gating.{}.linear_in,depformer.layers.{}.gating.{}.linear_out"

echo "Base model: $BASE_MODEL"
echo "Dataset: $DATASET"
echo "Output: $OUTPUT_DIR"
echo "LoRA rank: $RANK, alpha: $ALPHA"
echo "Batch size: $BATCH_SIZE (effective: $((BATCH_SIZE * GRAD_ACCUM)))"
echo "Max steps: $MAX_STEPS"

# Run training
python3 -m training.scripts.train_moshi_lora \
    --base_model "$BASE_MODEL" \
    --dataset_path "$DATASET" \
    --output_dir "$OUTPUT_DIR" \
    --lora_rank $RANK \
    --lora_alpha $ALPHA \
    --lora_dropout $DROPOUT \
    --learning_rate $LR \
    --per_device_train_batch_size $BATCH_SIZE \
    --gradient_accumulation_steps $GRAD_ACCUM \
    --max_steps $MAX_STEPS \
    --warmup_steps $WARMUP \
    --logging_steps 10 \
    --save_steps 200 \
    --eval_steps 100 \
    --logging_dir "$LOGGING_DIR" \
    --target_modules "$TARGET_MODULES" \
    --bf16 True \
    --gradient_checkpointing True \
    --resume_from_checkpoint False

echo "=== Training Complete ==="
echo "Adapter saved to: $OUTPUT_DIR"
