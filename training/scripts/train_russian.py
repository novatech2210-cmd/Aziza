#!/usr/bin/env python3
"""
train_russian.py — Aziza Russian QLoRA fine-tuning script
Novatech | AZIZA-BUILD-PLAN-PH2-PH3

Trains a QLoRA adapter on PersonaPlex-7B for Russian Cyrillic text generation.
Run in screen/tmux — training takes 12–18 hours on H100 SXM.

Usage:
    python3 train_russian.py --register colloquial \
        --dataset_path data/aziza-bilingual/aziza-bilingual.jsonl \
        --output_base /root/aziza/adapters

Locked config (do NOT change without team approval):
    LoRA r=16, alpha=32, 4-bit NF4, max_seq_len=512, batch=4, lr=2e-4
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# pyrefly: ignore [missing-import]
import torch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

LOCKED_CONFIG = {
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    "max_seq_length": 512,
    "batch_size": 4,
    "grad_accum_steps": 4,
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "warmup_steps": 100,
    "lr_scheduler_type": "cosine",
    "early_stop_patience": 3,
    "vram_oom_threshold_gb": 75.0,
}

VALID_REGISTERS = {"colloquial", "professional", "academic", "all"}
VALID_LANGUAGES = {"ru", "uz_latin", "uz_cyrillic"}
BASE_MODEL_ID = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train Russian QLoRA adapter for Aziza/PersonaPlex-7B"
    )
    p.add_argument(
        "--register",
        choices=list(VALID_REGISTERS),
        default="colloquial",
        help="Register to train on. 'all' = use all Russian data regardless of register.",
    )
    p.add_argument(
        "--language",
        choices=list(VALID_LANGUAGES),
        default="ru",
        help="Language variant to filter on.",
    )
    p.add_argument(
        "--dataset_path",
        required=True,
        help="Path to JSONL dataset file.",
    )
    p.add_argument(
        "--output_base",
        default="/root/aziza/adapters",
        help="Base directory for adapter output.",
    )
    p.add_argument(
        "--model_id",
        default=BASE_MODEL_ID,
        help="HuggingFace model ID for base model.",
    )
    p.add_argument(
        "--batch_size",
        type=int,
        default=LOCKED_CONFIG["batch_size"],
        help="Per-device batch size. Reduce to 2 if OOM.",
    )
    p.add_argument(
        "--grad_accum",
        type=int,
        default=LOCKED_CONFIG["grad_accum_steps"],
        help="Gradient accumulation steps. Increase to 8 if batch_size reduced.",
    )
    p.add_argument(
        "--max_seq_len",
        type=int,
        default=LOCKED_CONFIG["max_seq_length"],
        help="Maximum sequence length. Reduce to 256 for faster fallback run.",
    )
    p.add_argument(
        "--epochs",
        type=int,
        default=LOCKED_CONFIG["num_epochs"],
        help="Training epochs. Set to 1 for fast fallback run.",
    )
    p.add_argument(
        "--dry_run",
        action="store_true",
        help="Validate dataset and config only — do not start training.",
    )
    p.add_argument(
        "--resume_from",
        type=str,
        default=None,
        help="Path to checkpoint directory to resume training from.",
    )
    return p.parse_args()


# ── Dataset loading ────────────────────────────────────────────────────────────

def load_dataset_jsonl(
    path: str,
    language: str,
    register: str,
) -> list[dict]:
    """Load and filter JSONL dataset. Supports three field patterns from the spec."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    raw_records = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw_records.append(json.loads(line))
            except json.JSONDecodeError as e:
                log.warning(f"Skipping malformed JSON at line {i}: {e}")

    log.info(f"Loaded {len(raw_records):,} raw records from {path}")

    if not raw_records:
        raise ValueError(f"Dataset is empty: {path}")

    # Detect field pattern from first record
    sample = raw_records[0]
    if "messages" in sample:
        field_pattern = "messages"
    elif "instruction" in sample and "response" in sample:
        field_pattern = "instruction_response"
    elif "instruction" in sample and "output" in sample:
        field_pattern = "alpaca"
    elif "text" in sample:
        field_pattern = "text"
    elif "dialogue" in sample:
        field_pattern = "dialogue"
    else:
        raise ValueError(
            f"Unrecognised dataset format. Expected one of: messages, instruction+response, text, dialogue. "
            f"Got keys: {list(sample.keys())}"
        )
    log.info(f"Detected dataset format: '{field_pattern}'")

    # Filter by language and register
    filtered = []
    for rec in raw_records:
        rec_lang = rec.get("language", "")
        rec_reg = rec.get("register", "")

        lang_match = (not rec_lang) or (language in rec_lang)
        reg_match = (register == "all") or (not rec_reg) or (register in rec_reg)

        if lang_match and reg_match:
            filtered.append(rec)

    log.info(
        f"After filter (language={language}, register={register}): "
        f"{len(filtered):,} records"
    )

    if len(filtered) < 500:
        log.warning(
            f"Only {len(filtered)} records after filtering. "
            "Consider using --register all if too few examples survive the filter."
        )

    return filtered, field_pattern


def normalise_to_chatml(records: list[dict], field_pattern: str) -> list[dict]:
    """Normalise all field patterns to messages list (ChatML) format for SFTTrainer."""
    normalised = []
    for rec in records:
        if field_pattern == "messages":
            normalised.append({"messages": rec["messages"]})
        elif field_pattern == "instruction_response":
            normalised.append({
                "messages": [
                    {"role": "user", "content": rec["instruction"]},
                    {"role": "assistant", "content": rec["response"]},
                ]
            })
        elif field_pattern == "alpaca":
            user_msg = rec["instruction"]
            if rec.get("input"):
                user_msg += "\n\n" + rec["input"]
            normalised.append({
                "messages": [
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": rec["output"]},
                ]
            })
        elif field_pattern == "text":
            # Raw text — pass through as-is for SFTTrainer dataset_text_field
            normalised.append({"text": rec["text"]})
        elif field_pattern == "dialogue":
            # Example: "CLIENT (User): User query 0\nBROKER (Aziza): Привет..."
            dialogue = rec["dialogue"]
            parts = dialogue.split("\nBROKER (Aziza): ")
            user_msg = parts[0].replace("CLIENT (User): ", "").strip()
            assistant_msg = parts[1].strip() if len(parts) > 1 else ""
            
            messages = []
            if rec.get("system_prompt"):
                messages.append({"role": "system", "content": rec["system_prompt"]})
            messages.extend([
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ])
            normalised.append({"messages": messages})
    return normalised


def validate_cyrillic_coverage(records: list[dict], field_pattern: str, threshold: float = 0.6) -> float:
    """Sanity check: what fraction of assistant responses contain Cyrillic?"""
    cyrillic_range = range(0x0400, 0x0500)

    def has_cyrillic(text: str) -> bool:
        return any(ord(c) in cyrillic_range for c in text)

    total, with_cyrillic = 0, 0
    for rec in records:
        if field_pattern == "messages":
            for msg in rec.get("messages", []):
                if msg.get("role") == "assistant":
                    total += 1
                    if has_cyrillic(msg.get("content", "")):
                        with_cyrillic += 1
        elif field_pattern == "instruction_response":
            total += 1
            if has_cyrillic(rec.get("response", "")):
                with_cyrillic += 1
        elif field_pattern == "alpaca":
            total += 1
            if has_cyrillic(rec.get("output", "")):
                with_cyrillic += 1
        elif field_pattern == "dialogue":
            total += 1
            dialogue = rec.get("dialogue", "")
            parts = dialogue.split("\nBROKER (Aziza): ")
            assistant_msg = parts[1] if len(parts) > 1 else ""
            if has_cyrillic(assistant_msg):
                with_cyrillic += 1

    pct = (with_cyrillic / total) if total > 0 else 0.0
    log.info(f"Cyrillic coverage in assistant turns: {pct:.1%} ({with_cyrillic}/{total})")
    if pct < threshold:
        log.warning(
            f"Cyrillic coverage {pct:.1%} is below threshold {threshold:.0%}. "
            "Dataset may not be primarily Russian — check language filter."
        )
    return pct


# ── VRAM utilities ─────────────────────────────────────────────────────────────

def get_vram_used_gb() -> Optional[float]:
    """Return current VRAM usage in GB for device 0, or None if unavailable."""
    try:
        used = torch.cuda.memory_allocated(0)
        return used / (1024 ** 3)
    except Exception:
        return None


def check_vram_headroom(min_free_gb: float = 30.0) -> None:
    """Warn if VRAM headroom is insufficient before starting training."""
    if not torch.cuda.is_available():
        log.warning("No CUDA device detected — training will be very slow on CPU.")
        return
    total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    used_gb = get_vram_used_gb() or 0.0
    free_gb = total_gb - used_gb
    log.info(f"VRAM: {used_gb:.1f} GB used / {total_gb:.0f} GB total ({free_gb:.1f} GB free)")
    if free_gb < min_free_gb:
        raise RuntimeError(
            f"Insufficient VRAM headroom: {free_gb:.1f} GB free, need ≥ {min_free_gb} GB. "
            "Kill other processes using the GPU before starting training."
        )


# ── Training ───────────────────────────────────────────────────────────────────

def build_output_dir(output_base: str, language: str, register: str) -> Path:
    name = f"{language}_{register}" if register != "all" else f"{language}_all"
    out = Path(output_base) / name
    out.mkdir(parents=True, exist_ok=True)
    return out


def train(args: argparse.Namespace) -> None:
    # Late imports so --dry_run and argument validation work without GPU libs
    try:
        # pyrefly: ignore [missing-import]
        import datasets as hf_datasets
        # pyrefly: ignore [missing-import]
        from peft import LoraConfig, TaskType, get_peft_model
        # pyrefly: ignore [missing-import]
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            EarlyStoppingCallback,
        )
        # pyrefly: ignore [missing-import]
        from trl import SFTTrainer, SFTConfig
    except ImportError as e:
        log.error(
            f"Missing dependency: {e}\n"
            "Install with: pip install transformers peft trl bitsandbytes datasets accelerate"
        )
        sys.exit(1)

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        log.error("HF_TOKEN environment variable not set. Export it before running.")
        sys.exit(1)

    # ── Dataset ──────────────────────────────────────────────────────────────
    raw_records, field_pattern = load_dataset_jsonl(
        args.dataset_path, args.language, args.register
    )
    cyrillic_pct = validate_cyrillic_coverage(raw_records, field_pattern)
    normalised = normalise_to_chatml(raw_records, field_pattern)

    # Build HuggingFace Dataset with train/validation split
    hf_ds = hf_datasets.Dataset.from_list(normalised)
    split = hf_ds.train_test_split(test_size=0.05, seed=42)
    train_ds = split["train"]
    eval_ds = split["test"]
    log.info(f"Split: {len(train_ds):,} train / {len(eval_ds):,} eval")

    # ── Output directory ─────────────────────────────────────────────────────
    out_dir = build_output_dir(args.output_base, args.language, args.register)
    log.info(f"Adapter will be saved to: {out_dir}")

    # ── VRAM check ───────────────────────────────────────────────────────────
    check_vram_headroom(min_free_gb=30.0)

    # ── BitsAndBytes quantisation config ─────────────────────────────────────
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # ── Model + tokeniser ────────────────────────────────────────────────────
    log.info(f"Loading base model: {args.model_id}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_id, token=hf_token, trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        log.info("Set pad_token = eos_token")

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map="auto",
        token=hf_token,
        trust_remote_code=True,
    )
    model.config.use_cache = False  # Required for gradient checkpointing

    # ── LoRA config (LOCKED — do not change) ────────────────────────────────
    lora_cfg = LoraConfig(
        r=LOCKED_CONFIG["lora_r"],
        lora_alpha=LOCKED_CONFIG["lora_alpha"],
        target_modules=LOCKED_CONFIG["target_modules"],
        lora_dropout=LOCKED_CONFIG["lora_dropout"],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )

    # ── SFT training args ────────────────────────────────────────────────────
    run_name = f"ru_{args.register}_{int(time.time())}"
    sft_cfg = SFTConfig(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=LOCKED_CONFIG["learning_rate"],
        lr_scheduler_type=LOCKED_CONFIG["lr_scheduler_type"],
        warmup_steps=LOCKED_CONFIG["warmup_steps"],
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_dir=f"runs/{run_name}",
        logging_steps=10,
        bf16=True,
        gradient_checkpointing=True,
        report_to=["tensorboard"],
        run_name=run_name,
        max_length=args.max_seq_len,
        dataset_text_field="text" if field_pattern == "text" else None,
    )

    # ── Trainer ──────────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=sft_cfg,
        peft_config=lora_cfg,
        processing_class=tokenizer,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=LOCKED_CONFIG["early_stop_patience"]
            )
        ],
    )

    # ── Resume from checkpoint if specified ──────────────────────────────────
    resume_ckpt = args.resume_from or None
    if resume_ckpt:
        log.info(f"Resuming from checkpoint: {resume_ckpt}")

    log.info("=" * 60)
    log.info("TRAINING START")
    log.info(f"  Language : {args.language}")
    log.info(f"  Register : {args.register}")
    log.info(f"  Records  : {len(train_ds):,} train / {len(eval_ds):,} eval")
    log.info(f"  Epochs   : {args.epochs}")
    log.info(f"  Batch    : {args.batch_size} × {args.grad_accum} accum = effective {args.batch_size * args.grad_accum}")
    log.info(f"  Max seq  : {args.max_seq_len}")
    log.info(f"  LoRA r   : {LOCKED_CONFIG['lora_r']}, alpha: {LOCKED_CONFIG['lora_alpha']}")
    log.info(f"  Output   : {out_dir}")
    log.info("=" * 60)
    log.info("Monitor GPU: watch -n 10 nvidia-smi")
    log.info(f"TensorBoard: tensorboard --logdir runs --host 0.0.0.0 --port 6006")

    trainer.train(resume_from_checkpoint=resume_ckpt)

    # ── Save adapter ─────────────────────────────────────────────────────────
    log.info("Saving adapter...")
    trainer.model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    # Write README
    readme_path = out_dir / "README.md"
    with open(readme_path, "w") as f:
        f.write(f"# Aziza QLoRA Adapter — {args.language} / {args.register}\n\n")
        f.write(f"- Base model: `{args.model_id}`\n")
        f.write(f"- Language: `{args.language}`\n")
        f.write(f"- Register: `{args.register}`\n")
        f.write(f"- LoRA r: {LOCKED_CONFIG['lora_r']}, alpha: {LOCKED_CONFIG['lora_alpha']}\n")
        f.write(f"- Max seq length: {args.max_seq_len}\n")
        f.write(f"- Dataset: {args.dataset_path}\n")
        f.write(f"- Training records: {len(train_ds):,}\n")
        f.write(f"- Cyrillic coverage: {cyrillic_pct:.1%}\n")
        f.write(f"- Trained: {time.strftime('%Y-%m-%d %H:%M UTC')}\n")

    log.info(f"Adapter saved to: {out_dir}")
    log.info("Training complete. Run eval_russian.py before deploying.")


# ── Dry run ────────────────────────────────────────────────────────────────────

def dry_run(args: argparse.Namespace) -> None:
    log.info("DRY RUN — validating dataset and config only, not starting training")
    records, field_pattern = load_dataset_jsonl(
        args.dataset_path, args.language, args.register
    )
    validate_cyrillic_coverage(records, field_pattern)
    out_dir = build_output_dir(args.output_base, args.language, args.register)
    log.info(f"Output directory would be: {out_dir}")
    log.info(f"Effective batch size: {args.batch_size * args.grad_accum}")
    log.info(f"Estimated VRAM: 35–45 GB (H100 SXM 80GB — safe)")
    log.info("DRY RUN PASSED — safe to start training")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.dry_run:
        dry_run(args)
        return

    train(args)


if __name__ == "__main__":
    main()
