#!/bin/bash

# AZIZA Moshi - Phase 11 Curriculum Learning Pipeline
# This script automates the sequential fine-tuning of Moshi across multiple domains
# to prevent catastrophic forgetting and build nuanced personas.

set -e

# Default dataset paths
ACADEMIC_DATA="${1:-academic.jsonl}"
PROFESSIONAL_DATA="${2:-professional.jsonl}"
COLLOQUIAL_DATA="${3:-colloquial.jsonl}"
LANG_CODE="${4:-ru}"

echo "=========================================================="
echo " Starting Curriculum Learning Pipeline for Language: $LANG_CODE"
echo "=========================================================="
echo "Datasets:"
echo " 1. Academic:     $ACADEMIC_DATA"
echo " 2. Professional: $PROFESSIONAL_DATA"
echo " 3. Colloquial:   $COLLOQUIAL_DATA"
echo "=========================================================="

# ---------------------------------------------------------
# Step 1: Academic Style Fine-Tuning
# ---------------------------------------------------------
echo ""
echo "[STEP 1] Preparing Academic Dataset..."
if [ -f "$ACADEMIC_DATA" ]; then
    python3 prepare_dataset.py --input "$ACADEMIC_DATA" --lang "$LANG_CODE" --output_dir "./data_academic"
    echo "[STEP 1] Training Academic Baseline..."
    python3 finetune_moshi.py \
        --data_dir "./data_academic" \
        --output_dir "./aziza-adapter-academic-$LANG_CODE" \
        --epochs 3
else
    echo "Warning: Academic dataset ($ACADEMIC_DATA) not found. Skipping Step 1."
fi

# ---------------------------------------------------------
# Step 2: Professional Terms Fine-Tuning
# ---------------------------------------------------------
echo ""
echo "[STEP 2] Preparing Professional Dataset..."
if [ -f "$PROFESSIONAL_DATA" ]; then
    python3 prepare_dataset.py --input "$PROFESSIONAL_DATA" --lang "$LANG_CODE" --output_dir "./data_professional"
    
    RESUME_PATH=""
    if [ -d "./aziza-adapter-academic-$LANG_CODE/final" ]; then
        RESUME_PATH="--resume_from ./aziza-adapter-academic-$LANG_CODE/final"
        echo "[STEP 2] Resuming from Academic Baseline..."
    else
        echo "[STEP 2] No Academic Baseline found. Training from scratch..."
    fi

    echo "[STEP 2] Training Professional Vocabulary..."
    python3 finetune_moshi.py \
        --data_dir "./data_professional" \
        --output_dir "./aziza-adapter-professional-$LANG_CODE" \
        --epochs 3 \
        $RESUME_PATH
else
    echo "Warning: Professional dataset ($PROFESSIONAL_DATA) not found. Skipping Step 2."
fi

# ---------------------------------------------------------
# Step 3: Colloquial Style Fine-Tuning
# ---------------------------------------------------------
echo ""
echo "[STEP 3] Preparing Colloquial Dataset..."
if [ -f "$COLLOQUIAL_DATA" ]; then
    python3 prepare_dataset.py --input "$COLLOQUIAL_DATA" --lang "$LANG_CODE" --output_dir "./data_colloquial"
    
    RESUME_PATH=""
    if [ -d "./aziza-adapter-professional-$LANG_CODE/final" ]; then
        RESUME_PATH="--resume_from ./aziza-adapter-professional-$LANG_CODE/final"
        echo "[STEP 3] Resuming from Professional Checkpoint..."
    elif [ -d "./aziza-adapter-academic-$LANG_CODE/final" ]; then
        RESUME_PATH="--resume_from ./aziza-adapter-academic-$LANG_CODE/final"
        echo "[STEP 3] Resuming from Academic Baseline (Professional skipped)..."
    else
        echo "[STEP 3] No previous checkpoints found. Training from scratch..."
    fi

    echo "[STEP 3] Training Colloquial/Conversational Style..."
    python3 finetune_moshi.py \
        --data_dir "./data_colloquial" \
        --output_dir "./aziza-adapter-final-$LANG_CODE" \
        --epochs 3 \
        $RESUME_PATH
else
    echo "Warning: Colloquial dataset ($COLLOQUIAL_DATA) not found. Skipping Step 3."
fi

# ---------------------------------------------------------
# Step 4: Validation
# ---------------------------------------------------------
echo ""
echo "[STEP 4] Running TTFT & Overhead Benchmark..."
if [ -d "./aziza-adapter-final-$LANG_CODE/final" ]; then
    echo "Validating final adapter: ./aziza-adapter-final-$LANG_CODE/final"
    # Assuming benchmark_ttft.py accepts adapter_path, if not, it will run standard validation
    if grep -q "adapter_path" benchmark_ttft.py; then
        python3 benchmark_ttft.py --adapter_path "./aziza-adapter-final-$LANG_CODE/final"
    else
        python3 benchmark_ttft.py
    fi
else
    echo "Warning: Final adapter not found. Benchmark skipped."
fi

echo "=========================================================="
echo " Curriculum Learning Pipeline Complete."
echo " The final production-ready adapter is located at:"
echo " ./aziza-adapter-final-$LANG_CODE/final"
echo "=========================================================="
