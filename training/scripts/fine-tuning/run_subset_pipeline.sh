#!/bin/bash
set -e

echo "=========================================="
echo " Aziza Subset Audio & QLoRA Pipeline Test "
echo "=========================================="

export PYTHONPATH=/workspace/aziza-web/personaplex-finetune/VibeVoice:$PYTHONPATH
cd /workspace/aziza-web/personaplex-finetune

echo "1. Generating Voice Audio via VibeVoice..."
/workspace/aziza-web/.venv/bin/python pipeline/generate_audio.py \
  --model-path vibevoice/VibeVoice-7B \
  --dialogues data/aziza-bilingual/subset.jsonl \
  --output-dir data/aziza-bilingual/mono_wav \
  --scripts-dir data/aziza-bilingual/scripts \
  --voices-dir data/aziza-bilingual/speaker_samples \
  --gpus 0 \
  --batch-size 4

echo "2. Aligning and Channel Routing via WhisperX..."
/workspace/aziza-web/.venv/bin/python pipeline/create_stereo.py \
  --mono-dir data/aziza-bilingual/mono_wav \
  --scripts-dir data/aziza-bilingual/scripts \
  --output-dir data/aziza-bilingual/stereo_wav \
  --dialogues data/aziza-bilingual/subset.jsonl \
  --whisper-model large-v3 \
  --gpus 0 \
  --batch-size 4

echo "3. Extracting Injection Offsets..."
/workspace/aziza-web/.venv/bin/python pipeline/compute_injection_offsets.py \
  --stereo-dir data/aziza-bilingual/stereo_wav \
  --output data/aziza-bilingual/subset-offsets.jsonl

echo "4. Creating Training Manifest..."
/workspace/aziza-web/.venv/bin/python pipeline/create_manifest.py \
  --input data/aziza-bilingual/subset-offsets.jsonl \
  --output-dir data/aziza-bilingual/subset_dataset \
  --train-ratio 1.0

echo "Subset Pipeline Data Preparation Completed."
