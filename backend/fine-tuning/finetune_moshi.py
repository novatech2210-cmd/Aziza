"""
QLoRA Training script for Moshi text projection layers.
Phase 11 — Aziza Multilingual Curriculum Fine-Tuning
Supports: Academic → Professional → Colloquial sequential training.
"""
import os
import json
import argparse
import torch
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    BitsAndBytesConfig,
    TrainerCallback,
    Trainer,
    DataCollatorForLanguageModeling,
    EarlyStoppingCallback,
)
from peft import (
    LoraConfig,
    TaskType,
    get_peft_model,
    PeftModel,
    prepare_model_for_kbit_training,
)

# ---------------------------------------------------------------------------
# LOCKED CONFIG — do not change without benchmarking
# ---------------------------------------------------------------------------
LORA_CONFIG = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    # PASS 2: Includes audio codebooks for phonetic adaptation.
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj", "embed_tokens", "lm_head", "audio_emb", "out_audio", "audio_codebook_proj", "out_audio_proj"],
    bias="none",
)

BNB_CONFIG = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

# Base model — Moshi uses Helium (Mistral-based) as its text backbone
# We fine-tune the text backbone with QLoRA and keep audio codecs frozen.
BASE_MODEL_ID = os.getenv("BASE_MODEL_ID", "kyutai/moshika-pytorch-bf16")
TOKENIZER_ID  = os.getenv("TOKENIZER_ID", "kyutai/moshika-pytorch-bf16")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
class MemoryUsageCallback(TrainerCallback):
    """Log GPU memory usage every 50 steps."""
    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step % 50 == 0:
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / (1024 ** 3)
                reserved  = torch.cuda.memory_reserved()  / (1024 ** 3)
                print(
                    f"[GPU] Step {state.global_step}: "
                    f"Allocated={allocated:.2f}GB  Reserved={reserved:.2f}GB"
                )

class CheckpointCallback(TrainerCallback):
    """Save a 'latest' symlink after every checkpoint so resume is easy."""
    def on_save(self, args, state, control, **kwargs):
        latest = os.path.join(args.output_dir, "latest")
        ckpt   = os.path.join(args.output_dir, f"checkpoint-{state.global_step}")
        if os.path.exists(latest) or os.path.islink(latest):
            os.remove(latest)
        os.symlink(ckpt, latest)
        print(f"[Checkpoint] Saved step {state.global_step} → {ckpt}")

# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------
def load_jsonl(path: str) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def find_data_dir(data_dir: str, lang: str = "ru") -> dict[str, str]:
    """
    Look for train/val/test splits in <data_dir>/<lang>/ or <data_dir>/.
    Returns a dict with keys 'train', 'val', 'test' → file paths.
    """
    candidates = [
        os.path.join(data_dir, lang),
        data_dir,
    ]
    splits = {}
    for base in candidates:
        for split in ("train", "val", "test"):
            path = os.path.join(base, f"{split}.jsonl")
            if os.path.isfile(path) and split not in splits:
                splits[split] = path
    return splits


def build_hf_dataset(splits: dict[str, str], tokenizer, max_length: int = 512) -> dict[str, Dataset]:
    """Convert JSONL splits into tokenized HuggingFace Datasets."""
    hf = {}
    for split_name, path in splits.items():
        records = load_jsonl(path)
        texts = []
        for r in records:
            # Support multiple common formats
            if "text" in r:
                texts.append(r["text"])
            elif "messages" in r:
                # Chat format: list of {role, content}
                conversation = ""
                for msg in r["messages"]:
                    role    = msg.get("role", "user").upper()
                    content = msg.get("content", "")
                    conversation += f"<{role}> {content} </{role}>\n"
                texts.append(conversation.strip())
            elif "input" in r and "output" in r:
                texts.append(f"Input: {r['input']}\nOutput: {r['output']}")
            elif "prompt" in r and "completion" in r:
                texts.append(f"{r['prompt']}{r['completion']}")
            elif "ru" in r and "en" in r:
                texts.append(f"Russian: {r['ru']}\nEnglish: {r['en']}")
            else:
                # Best-effort: join all string values
                texts.append(" ".join(str(v) for v in r.values() if isinstance(v, str)))

        def tokenize(batch):
            return tokenizer(
                batch["text"],
                truncation=True,
                max_length=max_length,
                padding=False,
            )

        ds = Dataset.from_dict({"text": texts})
        ds = ds.map(tokenize, batched=True, remove_columns=["text"])
        hf[split_name] = ds
        print(f"  [{split_name}] {len(ds):,} examples loaded from {path}")
    return hf


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------
def train(output_dir: str, resume_from: str = None, data_dir: str = None, lang: str = "ru", epochs: int = 3):
    print("=" * 60)
    print(" AZIZA Phase 11 — QLoRA Curriculum Training")
    print(f" Output dir  : {output_dir}")
    print(f" Resume from : {resume_from or 'scratch'}")
    print(f" Data dir    : {data_dir or '(auto-detect)'}")
    print(f" Language    : {lang}")
    print("=" * 60)

    # -- Device / GPU check ------------------------------------------------
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Device] Using: {device}")
    if device == "cuda":
        print(f"[Device] GPU: {torch.cuda.get_device_name(0)}")
        print(f"[Device] VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # -- Load tokenizer ----------------------------------------------------
    print(f"\n[Model] Loading tokenizer from {TOKENIZER_ID} ...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            TOKENIZER_ID,
            trust_remote_code=True,
        )
    except Exception as e:
        print(f"[Info] AutoTokenizer failed ({e})")
        print(f"[Model] Loading Moshi's native SentencePiece tokenizer directly")
        import sentencepiece as spm
        from huggingface_hub import hf_hub_download
        
        spm_path = hf_hub_download(
            TOKENIZER_ID,
            "tokenizer_spm_32k_3.model",
            cache_dir="/root/aziza-build/model_cache",
        )
        sp = spm.SentencePieceProcessor(model_file=spm_path)
        
        # Wrap in minimal HF-compatible interface
        from transformers import PreTrainedTokenizer
        class MoshiSPMTokenizer(PreTrainedTokenizer):
            vocab_files_names = {"vocab_file": "tokenizer_spm_32k_3.model"}
            model_input_names = ["input_ids", "attention_mask"]
            
            def __init__(self, vocab_file=None, sp_processor=None, **kwargs):
                self.vocab_file = vocab_file
                if sp_processor is not None:
                    self.sp = sp_processor
                elif vocab_file:
                    self.sp = spm.SentencePieceProcessor(model_file=vocab_file)
                else:
                    raise ValueError("Need vocab_file or sp_processor")
                self._vocab_size = self.sp.vocab_size()
                super().__init__(**kwargs)
            
            @property
            def vocab_size(self):
                return self._vocab_size
            
            def get_vocab(self):
                return {self.sp.id_to_piece(i): i for i in range(self.vocab_size)}
            
            def _tokenize(self, text):
                return self.sp.encode(text, out_type=str)
            
            def _convert_token_to_id(self, token):
                return self.sp.piece_to_id(token)
            
            def _convert_id_to_token(self, index):
                if isinstance(index, int):
                    return self.sp.id_to_piece(index)
                return self.sp.id_to_piece(index.item() if hasattr(index, 'item') else int(index))
            
            def _decode(self, token_ids, skip_special_tokens=False, spaces_between_special_tokens=True, **kwargs):
                if isinstance(token_ids, int):
                    token_ids = [token_ids]
                if skip_special_tokens:
                    special_ids = {self.sp.piece_to_id(p) for p in ['<s>', '</s>', '<pad>', '<unk>']}
                    token_ids = [t for t in token_ids if t not in special_ids]
                return self.sp.decode(token_ids)
            
            def save_vocabulary(self, save_directory, filename_prefix=None):
                import shutil
                dst = os.path.join(save_directory, "tokenizer_spm_32k_3.model")
                shutil.copy(self.vocab_file, dst)
                return (dst,)
            
            @property
            def bos_token_id(self):
                return self.sp.bos_id()
            
            @property
            def eos_token_id(self):
                return self.sp.eos_id()
            
            @property
            def pad_token_id(self):
                return self.sp.pad_id() if self.sp.pad_id() >= 0 else self.sp.eos_id()
            
            @property
            def unk_token_id(self):
                return self.sp.unk_id()
        
        tokenizer = MoshiSPMTokenizer(sp_processor=sp)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # -- Load base model ---------------------------------------------------
    print(f"[Model] Loading base model ({BASE_MODEL_ID}) with 4-bit quantisation ...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_ID,
            quantization_config=BNB_CONFIG,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )
    except Exception as e:
        raise RuntimeError(f"[FATAL] Could not load base model {BASE_MODEL_ID}: {e}\n"
                         "This trainer only supports Moshi architecture. "
                         "Ensure model.safetensors is complete and not corrupted.")

    model = prepare_model_for_kbit_training(model)

    # -- Apply LoRA (or resume from existing adapter) ----------------------
    if resume_from and os.path.isdir(resume_from):
        print(f"[LoRA] Loading existing adapter from {resume_from}")
        model = PeftModel.from_pretrained(model, resume_from, is_trainable=True)
    else:
        print("[LoRA] Applying fresh LoRA adapter")
        model = get_peft_model(model, LORA_CONFIG)

    model.print_trainable_parameters()

    # -- Locate dataset ---------------------------------------------------
    if data_dir is None:
        # Try to find a data_* directory matching the last output_dir component
        tag = os.path.basename(output_dir).replace("aziza-adapter-", "").split("-")[0]
        data_dir = f"./data_{tag}"
        if not os.path.isdir(data_dir):
            data_dir = "./data"

    print(f"\n[Data] Scanning {data_dir} for split files ...")
    splits = find_data_dir(data_dir, lang)

    if not splits:
        raise FileNotFoundError(
            f"No JSONL split files found in {data_dir}. "
            "Expected train.jsonl / val.jsonl under <data_dir>/<lang>/ or <data_dir>/."
        )

    datasets = build_hf_dataset(splits, tokenizer)
    train_ds = datasets.get("train")
    eval_ds  = datasets.get("val") or datasets.get("test")

    # -- Training arguments -----------------------------------------------
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        bf16=device == "cuda",
        fp16=False,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        save_steps=100,
        logging_steps=10,
        eval_strategy="steps" if eval_ds else "no",
        eval_steps=100 if eval_ds else None,
        load_best_model_at_end=bool(eval_ds),
        dataloader_num_workers=4,
        report_to="none",
        remove_unused_columns=False,
        optim="paged_adamw_32bit",
        max_grad_norm=0.3,
    )

    callbacks = [MemoryUsageCallback(), CheckpointCallback()]
    if eval_ds:
        callbacks.append(EarlyStoppingCallback(early_stopping_patience=3))

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        callbacks=callbacks,
    )

    # -- Train! ------------------------------------------------------------
    print("\n[Training] Starting training run ...")
    trainer.train()

    # -- Save final adapter -----------------------------------------------
    final_output_dir = os.path.join(output_dir, "final")
    os.makedirs(final_output_dir, exist_ok=True)
    trainer.model.save_pretrained(final_output_dir)
    tokenizer.save_pretrained(final_output_dir)
    print(f"\n[Done] Adapter saved to {final_output_dir}")
    print("Run benchmark_ttft.py to verify TTFT overhead is <10ms.")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AZIZA Phase 11 QLoRA fine-tuning")
    parser.add_argument("--output_dir",   default="./aziza-multilingual-adapter",
                        help="Directory to save the adapter")
    parser.add_argument("--resume_from",  default=None,
                        help="Path to previous adapter checkpoint to resume from")
    parser.add_argument("--data_dir",     default=None,
                        help="Directory containing train/val/test JSONL splits")
    parser.add_argument("--lang",         default="ru",
                        help="Language code (default: ru)")
    parser.add_argument("--epochs",       default=3, type=int,
                        help="Number of training epochs (default: 3)")
    args = parser.parse_args()

    train(args.output_dir, args.resume_from, args.data_dir, args.lang, args.epochs)
