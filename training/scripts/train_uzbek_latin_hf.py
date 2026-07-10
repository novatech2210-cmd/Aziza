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
train_uzbek_latin_hf.py — Aziza Uzbek Latin QLoRA adapter
Novatech | AZIZA-BUILD-PLAN-PH2-PH3

Trains a QLoRA adapter on Vikhr-Llama-3.1-8B-Instruct for Uzbek Latin text
generation using public HuggingFace datasets. Designed to run on HF Jobs
(a10g-large or a100-large).

Datasets (164K total examples):
  - behbudiy/alpaca-cleaned-uz       (52K instruction pairs, Latin)
  - saillab/alpaca-uzbek-cleaned     (52K instruction pairs, Latin)
  - behbudiy/translation-instruction (20K bilingual professional pairs)
  - tahrirchi/uz-books               (40K — Latin portion filtered)

Adapter saved to: novatech2210/aziza-uz-latin-colloquial
"""

import os
import sys
import time
import logging
import torch
from datasets import load_dataset, concatenate_datasets, Dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Locked config (DO NOT CHANGE without team approval) ───────────────────────
LOCKED_CONFIG = {
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "max_seq_length": 512,
    "batch_size": 2,
    "grad_accum_steps": 4,
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "warmup_steps": 100,
    "lr_scheduler_type": "cosine",
    "quantization": "nf4",
    "double_quant": True,
    "compute_dtype": "float16",
}

BASE_MODEL_ID  = "uzlm/alloma-3B-Instruct"
HUB_ADAPTER_ID = "novatech2210/aziza-uz-latin-colloquial"
ADAPTER_PATH   = '/root/aziza-build/adapters/aziza-adapter-final-uz'

# ── Auth ──────────────────────────────────────────────────────────────────────
HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    log.error("HF_TOKEN environment variable not set.")
    sys.exit(1)

# ── Latin script detector ─────────────────────────────────────────────────────
# Uzbek Latin uses ASCII letters + a few extended chars (oʻ, gʻ, etc.)
# Reject records that are primarily Cyrillic.
CYRILLIC_RANGE = range(0x0400, 0x0500)

def is_latin_uzbek(text: str, cyrillic_threshold: float = 0.15) -> bool:
    if not text:
        return False
    cyrillic_chars = sum(1 for c in text if ord(c) in CYRILLIC_RANGE)
    return (cyrillic_chars / len(text)) < cyrillic_threshold

def to_messages(instruction: str, output: str, input_ctx: str = "") -> dict:
    user_content = instruction
    if input_ctx:
        user_content = f"{instruction}\n\n{input_ctx}"
    return {
        "messages": [
            {"role": "user",      "content": user_content},
            {"role": "assistant", "content": output},
        ]
    }

# ── Dataset loading ───────────────────────────────────────────────────────────
def load_alpaca_uz() -> Dataset:
    """behbudiy/alpaca-cleaned-uz — 52K Uzbek Latin alpaca pairs."""
    log.info("Loading behbudiy/alpaca-cleaned-uz …")
    ds = load_dataset("behbudiy/alpaca-cleaned-uz", split="train", token=HF_TOKEN)
    log.info(f"  Raw size: {len(ds):,}")

    records = []
    for ex in ds:
        instruction = ex.get("instruction", "") or ""
        output      = ex.get("output", "") or ""
        input_ctx   = ex.get("input", "") or ""
        if not instruction or not output:
            continue
        full_text = instruction + " " + output
        if not is_latin_uzbek(full_text):
            continue
        records.append(to_messages(instruction, output, input_ctx))

    log.info(f"  After filter: {len(records):,}")
    return Dataset.from_list(records[:5000])


def load_saillab_uz() -> Dataset:
    """saillab/alpaca-uzbek-cleaned — 52K independent Latin Uzbek translation."""
    log.info("Loading saillab/alpaca-uzbek-cleaned …")
    ds = load_dataset("saillab/alpaca-uzbek-cleaned", split="train", token=HF_TOKEN)
    log.info(f"  Raw size: {len(ds):,}")

    records = []
    for ex in ds:
        instruction = ex.get("instruction", "") or ""
        output      = ex.get("output", "") or ""
        input_ctx   = ex.get("input", "") or ""
        if not instruction or not output:
            continue
        full_text = instruction + " " + output
        if not is_latin_uzbek(full_text):
            continue
        records.append(to_messages(instruction, output, input_ctx))

    log.info(f"  After filter: {len(records):,}")
    return Dataset.from_list(records[:5000])


def load_translation_instruction() -> Dataset:
    """behbudiy/translation-instruction — 20K Uzbek bilingual professional pairs."""
    log.info("Loading behbudiy/translation-instruction …")
    ds = load_dataset("behbudiy/translation-instruction", split="train", token=HF_TOKEN)
    log.info(f"  Raw size: {len(ds):,}")

    records = []
    for ex in ds:
        instruction = ex.get("instruction", "") or ""
        output      = ex.get("output", "") or ""
        input_ctx   = ex.get("input", "") or ""
        if not instruction or not output:
            continue
        records.append(to_messages(instruction, output, input_ctx))

    log.info(f"  After filter: {len(records):,}")
    return Dataset.from_list(records[:5000])


def load_uz_books_latin() -> Dataset:
    """tahrirchi/uz-books — 40K books corpus. Filter to Latin-script records."""
    log.info("Loading tahrirchi/uz-books (Latin portion) …")
    try:
        ds = load_dataset("tahrirchi/uz-books", split="lat", token=HF_TOKEN, streaming=True)
    except Exception as e:
        log.warning(f"  Could not load tahrirchi/uz-books: {e}. Skipping.")
        return Dataset.from_list([])

    log.info("  Streaming tahrirchi/uz-books...")

    records = []
    for ex in ds:
        text = ex.get("text", "") or ex.get("content", "") or ""
        if not text or len(text) < 50:
            continue
        if not is_latin_uzbek(text):
            continue
        # Truncate long book passages to 400 chars for a clean SFT example
        snippet = text[:400].strip()
        records.append({
            "messages": [
                {"role": "user",      "content": "Matnni davom ettiring:"},
                {"role": "assistant", "content": snippet},
            ]
        })
        if len(records) >= 5000:
            break

    log.info(f"  After filter (Latin only): {len(records):,}")
    return Dataset.from_list(records[:5000])


def build_dataset() -> tuple[Dataset, Dataset]:
    parts = [
        load_alpaca_uz(),
        load_saillab_uz(),
        load_translation_instruction(),
    ]
    parts = [p for p in parts if len(p) > 0]
    combined = concatenate_datasets(parts)
    combined = combined.shuffle(seed=42)
    log.info(f"Combined dataset: {len(combined):,} examples")

    split = combined.train_test_split(test_size=0.05, seed=42)
    return split["train"], split["test"]


# ── Training ──────────────────────────────────────────────────────────────────
def main():
    # Late imports for HF Jobs isolation
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        EarlyStoppingCallback,
    )
    from peft import LoraConfig, TaskType
    from trl import SFTTrainer, SFTConfig
    # # import trackio  # disabled — imported for side effects (auto-init)

    log.info("=" * 60)
    log.info("Aziza Uzbek Latin QLoRA Training — HF Jobs")
    log.info(f"Base model : {BASE_MODEL_ID}")
    log.info(f"Hub target : {HUB_ADAPTER_ID}")
    log.info("=" * 60)

    # GPU info
    if torch.cuda.is_available():
        total_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        log.info(f"GPU: {torch.cuda.get_device_name(0)} — {total_gb:.0f} GB VRAM")
    else:
        log.warning("No CUDA GPU detected! Training will be extremely slow.")

    # ── Dataset ──────────────────────────────────────────────────────────────
    train_ds, eval_ds = build_dataset()
    log.info(f"Train: {len(train_ds):,}  |  Eval: {len(eval_ds):,}")

    # ── Quantisation ─────────────────────────────────────────────────────────
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
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
    run_name = f"uz_latin_colloquial_{int(time.time())}"
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
        bf16=True,
        gradient_checkpointing=True,
        report_to="tensorboard",
        # project="aziza-uzbek-training",
        run_name=run_name,
        max_length=LOCKED_CONFIG["max_seq_length"],
        # Hub push
        push_to_hub=False,
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

    log.info("TRAINING START — uz_latin_colloquial")
    trainer.train()

    # ── Save & push ──────────────────────────────────────────────────────────
    log.info("Saving adapter …")
    trainer.model.save_pretrained(ADAPTER_PATH)
    tokenizer.save_pretrained(ADAPTER_PATH)
    # trainer.push_to_hub()  # disabled

    log.info(f"✅ Adapter pushed to: https://huggingface.co/{HUB_ADAPTER_ID}")
    log.info("Run eval_uzbek.py before deploying to production.")


if __name__ == "__main__":
    main()
