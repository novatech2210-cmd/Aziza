#!/usr/bin/env python3
"""
Uzbek WER/CER Evaluation Pipeline for AZIZA Voice Assistant.

Usage:
    python3 uzbek_wer_evaluation.py --audio_dir /path/to/audio --ground_truth transcriptions.jsonl
    python3 uzbek_wer_evaluation.py --benchmark aziza-uzbek-val --model whisper-base

Requirements:
    - Audio files paired with ground truth transcriptions
    - faster-whisper for ASR
    - jiwer for WER calculation
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from faster_whisper import WhisperModel
from jiwer import wer, cer


def load_ground_truth(path: Path) -> Dict[str, str]:
    """Load ground truth transcriptions from JSONL file.
    
    Expected format:
    {"audio_path": "audio/001.wav", "text": "Salom, qanday kelibsiz?"}
    """
    truths = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            audio = row.get("audio_path") or row.get("audio") or row.get("file")
            text = row.get("text") or row.get("transcription") or row.get("ground_truth")
            if audio and text:
                truths[audio] = text
    return truths


def compute_metrics(references: List[str], hypotheses: List[str]) -> Dict[str, float]:
    """Compute WER and CER metrics."""
    if not references or not hypotheses:
        return {"wer": 0.0, "cer": 0.0, "samples": 0}
    
    wer_score = wer(references, hypotheses)
    cer_score = cer(references, hypotheses)
    
    return {
        "wer": round(float(wer_score), 4),
        "cer": round(float(cer_score), 4),
        "samples": len(references),
    }


def transcribe_audio(model: WhisperModel, audio_path: str, language: str = "uz") -> Tuple[str, float]:
    """Transcribe a single audio file and return (text, latency_ms)."""
    start = time.perf_counter()
    
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        language=language,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    
    text = " ".join(segment.text.strip() for segment in segments)
    latency_ms = (time.perf_counter() - start) * 1000
    
    return text, latency_ms


def evaluate_dataset(
    model: WhisperModel,
    ground_truth: Dict[str, str],
    audio_dir: Path,
    language: str = "uz",
) -> Dict:
    """Run ASR evaluation on a dataset."""
    results = []
    references = []
    hypotheses = []
    latencies = []
    
    for audio_file, expected_text in ground_truth.items():
        audio_path = audio_dir / audio_file
        if not audio_path.exists():
            print(f"  [SKIP] Missing audio: {audio_path}")
            continue
        
        try:
            predicted_text, latency_ms = transcribe_audio(model, str(audio_path), language)
            references.append(expected_text)
            hypotheses.append(predicted_text)
            latencies.append(latency_ms)
            
            results.append({
                "audio": str(audio_file),
                "expected": expected_text,
                "predicted": predicted_text,
                "latency_ms": round(latency_ms, 2),
            })
            print(f"  [{len(results)}/{len(ground_truth)}] {audio_file}: {predicted_text[:60]}...")
        except Exception as e:
            print(f"  [ERROR] {audio_file}: {e}")
    
    metrics = compute_metrics(references, hypotheses)
    
    return {
        "model": model.model_name,
        "language": language,
        "metrics": metrics,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Uzbek WER/CER Evaluation")
    parser.add_argument("--audio_dir", type=str, default="datasets/uzbek/audio",
                        help="Directory containing audio files")
    parser.add_argument("--ground_truth", type=str, default="datasets/uzbek/transcriptions.jsonl",
                        help="JSONL file with ground truth transcriptions")
    parser.add_argument("--model", type=str, default="base",
                        help="Whisper model size: tiny, base, small, medium, large")
    parser.add_argument("--language", type=str, default="uz",
                        help="Language code for transcription")
    parser.add_argument("--output", type=str, default="reports/uzbek_wer_report.json",
                        help="Output JSON report path")
    parser.add_argument("--device", type=str, default="cpu",
                        help="Device: cpu, cuda")
    args = parser.parse_args()
    
    audio_dir = Path(args.audio_dir)
    gt_path = Path(args.ground_truth)
    
    if not gt_path.exists():
        print(f"Ground truth file not found: {gt_path}")
        print("Please create a JSONL file with format: {\"audio_path\": \"...\", \"text\": \"...\"}")
        sys.exit(1)
    
    if not audio_dir.exists():
        print(f"Audio directory not found: {audio_dir}")
        print("Please place audio files in the specified directory")
        sys.exit(1)
    
    print(f"Loading Whisper model: {args.model}")
    compute_type = "float16" if args.device == "cuda" else "int8"
    model = WhisperModel(args.model, device=args.device, compute_type=compute_type)
    
    print(f"Loading ground truth from: {gt_path}")
    ground_truth = load_ground_truth(gt_path)
    print(f"Loaded {len(ground_truth)} transcriptions")
    
    if not ground_truth:
        print("No valid transcriptions found. Exiting.")
        sys.exit(1)
    
    print(f"Running evaluation on {len(ground_truth)} samples...")
    report = evaluate_dataset(model, ground_truth, audio_dir, args.language)
    
    # Save report
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport saved to: {out_path}")
    print(f"WER: {report['metrics']['wer']:.2%}")
    print(f"CER: {report['metrics']['cer']:.2%}")
    print(f"Avg latency: {report['avg_latency_ms']:.1f}ms")
    
    # Exit with appropriate code
    target_wer = 0.15
    target_cer = 0.05
    if report['metrics']['wer'] > target_wer or report['metrics']['cer'] > target_cer:
        print(f"\nWARNING: Metrics exceed target (WER<{target_wer:.0%}, CER<{target_cer:.0%})")
        sys.exit(1)
    else:
        print(f"\nPASS: Metrics within target (WER<{target_wer:.0%}, CER<{target_cer:.0%})")
        sys.exit(0)


if __name__ == "__main__":
    main()
