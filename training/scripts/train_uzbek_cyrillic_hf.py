# /// script
# dependencies = [
#   "torch>=2.1.0",
#   "transformers>=4.45.0",
#   "peft>=0.13.0",
#   "trl>=0.12.0",
#   "bitsandbytes>=0.43.0",
#   "datasets>=2.21.0",
#   "accelerate>=0.34.0",
#   "trackio",
#   "huggingface_hub>=0.24.0",
# ]
# ///
"""
train_uzbek_cyrillic_hf.py — Aziza Uzbek Cyrillic QLoRA adapter
Novatech | AZIZA-BUILD-PLAN-PH2-PH3

Trains a QLoRA adapter on Vikhr-Llama-3.1-8B-Instruct for Uzbek Cyrillic
text generation using public HuggingFace datasets. Designed to run on HF
Jobs (a10g-large or a100-large).

Primary dataset:
  - tahrirchi/uz-books  (40K books, Cyrillic portion)
  - behbudiy/alpaca-cleaned-uz filtered to Cyrillic rows (fallback)

Adapter saved to: novatech2210/aziza-uz-cyrillic-colloquial
"""

import os
import sys
import time
import logging
# pyrefly: ignore [missing-import]
import torch
# pyrefly: ignore [missing-import]
from datasets import load_dataset, concatenate_datasets, Dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Locked config (DO NOT CHANGE without team approval) ───────────────────────
LOCKED_CONFIG = {
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "max_seq_length": 512,
    "batch_size": 4,
    "grad_accum_steps": 4,
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "warmup_steps": 100,
    "lr_scheduler_type": "cosine",
    "quantization": "nf4",
    "double_quant": True,
    "compute_dtype": "float16",
}

BASE_MODEL_ID  = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
HUB_ADAPTER_ID = "novatech2210/aziza-uz-cyrillic-colloquial"
ADAPTER_PATH   = "/tmp/aziza-uz-cyrillic"

# ── Auth ──────────────────────────────────────────────────────────────────────
HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    log.error("HF_TOKEN environment variable not set.")
    sys.exit(1)

# ── Cyrillic script detector ──────────────────────────────────────────────────
CYRILLIC_RANGE = range(0x0400, 0x0500)

def is_cyrillic_uzbek(text: str, cyrillic_threshold: float = 0.25) -> bool:
    """Return True if text has sufficient Cyrillic to be Uzbek Cyrillic."""
    if not text or len(text) < 10:
        return False
    cyrillic_chars = sum(1 for c in text if ord(c) in CYRILLIC_RANGE)
    return (cyrillic_chars / len(text)) >= cyrillic_threshold

def validate_cyrillic_pct(records: list[dict]) -> float:
    total, cyrillic = 0, 0
    for rec in records:
        for msg in rec.get("messages", []):
            if msg.get("role") == "assistant":
                total += 1
                if is_cyrillic_uzbek(msg.get("content", ""), cyrillic_threshold=0.15):
                    cyrillic += 1
    pct = cyrillic / total if total > 0 else 0.0
    log.info(f"Cyrillic coverage in assistant turns: {pct:.1%} ({cyrillic}/{total})")
    return pct

# ── Dataset loading ───────────────────────────────────────────────────────────
def load_uz_books_cyrillic() -> Dataset:
    """tahrirchi/uz-books — 40K books, Cyrillic portion only."""
    log.info("Loading tahrirchi/uz-books (Cyrillic portion) …")
    try:
        ds = load_dataset("tahrirchi/uz-books", split="original", token=HF_TOKEN, streaming=True)
    except Exception as e:
        log.warning(f"  Could not load tahrirchi/uz-books: {e}. Skipping.")
        return Dataset.from_list([])

    log.info("  Streaming tahrirchi/uz-books...")

    records = []
    for ex in ds:
        text = ex.get("text", "") or ex.get("content", "") or ""
        if not text or len(text) < 50:
            continue
        if not is_cyrillic_uzbek(text):
            continue
        # Use up to 400 chars as a continuation prompt
        snippet = text[:400].strip()
        records.append({
            "messages": [
                {"role": "user",      "content": "Matnni davom ettiring (кириллча):"},
                {"role": "assistant", "content": snippet},
            ]
        })
        if len(records) >= 5000:
            break

    log.info(f"  After Cyrillic filter: {len(records):,}")
    return Dataset.from_list(records)


def load_alpaca_uz_cyrillic() -> Dataset:
    """behbudiy/alpaca-cleaned-uz filtered to Cyrillic rows (minority portion)."""
    log.info("Loading behbudiy/alpaca-cleaned-uz (Cyrillic rows) …")
    try:
        ds = load_dataset("behbudiy/alpaca-cleaned-uz", split="train", token=HF_TOKEN)
    except Exception as e:
        log.warning(f"  Could not load alpaca-cleaned-uz: {e}. Skipping.")
        return Dataset.from_list([])

    log.info(f"  Raw size: {len(ds):,}")

    records = []
    for ex in ds:
        instruction = ex.get("instruction", "") or ""
        output      = ex.get("output", "") or ""
        input_ctx   = ex.get("input", "") or ""
        if not instruction or not output:
            continue
        full_text = instruction + " " + output
        if not is_cyrillic_uzbek(full_text):
            continue
        user_content = instruction
        if input_ctx:
            user_content = f"{instruction}\n\n{input_ctx}"
        records.append({
            "messages": [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": output},
            ]
        })

    log.info(f"  After Cyrillic filter: {len(records):,}")
    return Dataset.from_list(records)


def load_saillab_cyrillic() -> Dataset:
    """saillab/alpaca-uzbek-cleaned filtered to Cyrillic rows."""
    log.info("Loading saillab/alpaca-uzbek-cleaned (Cyrillic rows) …")
    try:
        ds = load_dataset("saillab/alpaca-uzbek-cleaned", split="train", token=HF_TOKEN)
    except Exception as e:
        log.warning(f"  Could not load saillab dataset: {e}. Skipping.")
        return Dataset.from_list([])

    log.info(f"  Raw size: {len(ds):,}")

    records = []
    for ex in ds:
        instruction = ex.get("instruction", "") or ""
        output      = ex.get("output", "") or ""
        input_ctx   = ex.get("input", "") or ""
        if not instruction or not output:
            continue
        full_text = instruction + " " + output
        if not is_cyrillic_uzbek(full_text):
            continue
        user_content = instruction
        if input_ctx:
            user_content = f"{instruction}\n\n{input_ctx}"
        records.append({
            "messages": [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": output},
            ]
        })

    log.info(f"  After Cyrillic filter: {len(records):,}")
    return Dataset.from_list(records)


def build_dataset() -> tuple[Dataset, Dataset]:
    parts = [
        load_uz_books_cyrillic(),       # Primary source (~40K Cyrillic books)
        load_alpaca_uz_cyrillic(),       # Supplementary Cyrillic alpaca rows
        load_saillab_cyrillic(),         # Additional Cyrillic rows
    ]
    parts = [p for p in parts if len(p) > 0]

    if not parts:
        log.error("All dataset sources empty or failed. Cannot continue.")
        sys.exit(1)

    combined = concatenate_datasets(parts)
    combined = combined.shuffle(seed=42)
    log.info(f"Combined Cyrillic dataset: {len(combined):,} examples")

    # Quality check
    cyrillic_pct = validate_cyrillic_pct(combined.to_list())
    if cyrillic_pct < 0.50:
        log.warning(
            f"Cyrillic coverage {cyrillic_pct:.1%} is below 50%! "
            "Dataset may be predominantly Latin. Check filters."
        )

    split = combined.train_test_split(test_size=0.05, seed=42)
    return split["train"], split["test"]


# ── Training ──────────────────────────────────────────────────────────────────
def main():
    # pyrefly: ignore [missing-import]
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        EarlyStoppingCallback,
    )
    # pyrefly: ignore [missing-import]
    from peft import LoraConfig, TaskType
    # pyrefly: ignore [missing-import]
    from trl import SFTTrainer, SFTConfig
    # pyrefly: ignore [missing-import]
    import trackio  # noqa: F401

    log.info("=" * 60)
    log.info("Aziza Uzbek Cyrillic QLoRA Training — HF Jobs")
    log.info(f"Base model : {BASE_MODEL_ID}")
    log.info(f"Hub target : {HUB_ADAPTER_ID}")
    log.info("=" * 60)

    if torch.cuda.is_available():
        total_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        log.info(f"GPU: {torch.cuda.get_device_name(0)} — {total_gb:.0f} GB VRAM")
    else:
        log.warning("No CUDA GPU detected!")

    # ── Dataset ──────────────────────────────────────────────────────────────
    train_ds, eval_ds = build_dataset()
    log.info(f"Train: {len(train_ds):,}  |  Eval: {len(eval_ds):,}")

    # ── Quantisation ─────────────────────────────────────────────────────────
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    # ── Tokeniser ────────────────────────────────────────────────────────────
    log.info(f"Loading tokeniser: {BASE_MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_ID, token=HF_TOKEN, trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── Model ─────────────────────────────────────────────────────────────────
    log.info(f"Loading model: {BASE_MODEL_ID}")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        token=HF_TOKEN,
        trust_remote_code=True,
    )
    model.config.use_cache = False

    # ── LoRA (LOCKED — do not change) ────────────────────────────────────────
    lora_cfg = LoraConfig(
        r=LOCKED_CONFIG["lora_r"],
        lora_alpha=LOCKED_CONFIG["lora_alpha"],
        target_modules=LOCKED_CONFIG["target_modules"],
        lora_dropout=LOCKED_CONFIG["lora_dropout"],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )

    # ── SFT config ───────────────────────────────────────────────────────────
    run_name = f"uz_cyrillic_colloquial_{int(time.time())}"
    sft_cfg = SFTConfig(
        output_dir=ADAPTER_PATH,
        num_train_epochs=LOCKED_CONFIG["num_epochs"],
        per_device_train_batch_size=LOCKED_CONFIG["batch_size"],
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=LOCKED_CONFIG["grad_accum_steps"],
        learning_rate=LOCKED_CONFIG["learning_rate"],
        lr_scheduler_type=LOCKED_CONFIG["lr_scheduler_type"],
        warmup_steps=LOCKED_CONFIG["warmup_steps"],
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=20,
        fp16=True,
        gradient_checkpointing=True,
        report_to="trackio",
        project="aziza-uzbek-training",
        run_name=run_name,
        max_length=LOCKED_CONFIG["max_seq_length"],
        # Hub push
        push_to_hub=True,
        hub_model_id=HUB_ADAPTER_ID,
        hub_strategy="every_save",
    )

    # ── Trainer ──────────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=sft_cfg,
        peft_config=lora_cfg,
        processing_class=tokenizer,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    log.info("TRAINING START — uz_cyrillic_colloquial")
    trainer.train()

    # ── Save & push ──────────────────────────────────────────────────────────
    log.info("Saving adapter …")
    trainer.model.save_pretrained(ADAPTER_PATH)
    tokenizer.save_pretrained(ADAPTER_PATH)
    trainer.push_to_hub()

    log.info(f"✅ Adapter pushed to: https://huggingface.co/{HUB_ADAPTER_ID}")
    log.info("Run eval_uzbek.py before deploying to production.")


if __name__ == "__main__":
    main()
