#!/bin/bash
set -e

echo "=========================================="
echo " Aziza Multilingual Audio & QLoRA Pipeline "
echo "=========================================="

export PYTHONPATH=/workspace/aziza-web/personaplex-finetune/VibeVoice:$PYTHONPATH
cd /workspace/aziza-web/personaplex-finetune

echo "1. Generating Voice Audio via VibeVoice..."
/workspace/aziza-web/.venv/bin/python pipeline/generate_audio.py \
  --model-path vibevoice/VibeVoice-7B \
  --dialogues data/aziza-bilingual/aziza-bilingual.jsonl \
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
  --dialogues data/aziza-bilingual/aziza-bilingual.jsonl \
  --whisper-model large-v3 \
  --gpus 0 \
  --batch-size 4

echo "3. Extracting Injection Offsets..."
/workspace/aziza-web/.venv/bin/python pipeline/compute_injection_offsets.py \
  --stereo-dir data/aziza-bilingual/stereo_wav \
  --output data/aziza-bilingual/aziza-bilingual-offsets.jsonl

echo "4. Creating Training Manifest..."
/workspace/aziza-web/.venv/bin/python pipeline/create_manifest.py \
  --input data/aziza-bilingual/aziza-bilingual-offsets.jsonl \
  --output-dir data/aziza-bilingual/dataset \
  --train-ratio 0.95

echo "5. Initiating QLoRA Training..."
/workspace/aziza-web/.venv/bin/python moshi-finetune/train.py \
  --config /workspace/aziza-web/.planning/phases/phase-1-voice-pipeline/bilingual_aziza.yaml

echo "Pipeline Initiated/Completed Successfully."
