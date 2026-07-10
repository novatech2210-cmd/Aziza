"""
QLoRA Training script for Moshi text projection layers.
Phase 11 — Aziza Multilingual Curriculum Fine-Tuning
Supports: Academic → Professional → Colloquial sequential training.
"""
import os
import json
import argparse
import torch
import torch.nn as nn
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    PreTrainedModel,
    PretrainedConfig,
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
# IMPORTANT: Moshi uses a custom transformer architecture (Helium/StreamingLM).
# Its attention and FFN layers do NOT use the standard Llama module names
# (q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj).
#
# Actual Moshi LM linear module names (confirmed by model graph inspection):
#   in_projs   → fused Q+K+V input projection (replaces q/k/v_proj in Llama)
#   out_projs  → attention output projection   (replaces o_proj in Llama)
#   linear_in  → gating FFN input              (inside self_attn.gating)
#   linear_out → gating FFN output             (inside self_attn.gating)
#   text_linear→ text token head projection
#
# Using Llama module names on a Moshi model will cause:
#   "Target modules {'q_proj', ...} not found in the base model."
# ---------------------------------------------------------------------------
# IMPORTANT: in_projs and out_projs are nn.ModuleList objects containing one
# Linear each.  PEFT cannot inject into ModuleList directly; it must target
# the indexed child.  The correct PEFT target_modules are therefore the
# *suffix* of the full module path:
#   moshi_lm.transformer.layers.N.self_attn.in_projs.0   → suffix "0"  ← too broad
# Instead we use the parent+index pattern via a regex or by listing the
# concrete children.  PEFT's `target_modules` accepts regex strings, so we
# can match "in_projs\.\d+" to hit all indexed children.
LORA_CONFIG = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    # IMPORTANT: target_modules must be a single STRING for PEFT to treat it
    # as a regex (re.fullmatch against the full dotted module name). A LIST
    # of regex-looking strings is matched LITERALLY per entry and will never
    # match real module names -- this was the bug that caused
    # "Target modules {...} not found in the base model" during validation.
    # Confirmed working against the real module tree (in_projs.0, out_projs.0
    # inside indexed ModuleLists; linear_in/linear_out included defensively
    # in case they exist elsewhere in the architecture -- harmless no-op if not).
    target_modules=r".*\.(in_projs|out_projs)\.\d+$|.*(linear_in|linear_out)$",
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

# Fallback to a smaller open model if Moshi weights aren't available
FALLBACK_MODEL_ID = "mistralai/Mistral-7B-v0.1"

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
    # Loads the VOCAB-EXTENDED tokenizer (32016 tokens: original 32000 +
    # placeholder at 32000 + 15 new Uzbek/Cyrillic graphemes at 32001-32015).
    # Confirmed zero fragmentation on Oʻ/Gʻ/Ҳ/Ҷ/Қ/Ғ/Ў and lowercase forms via
    # audit_tokenizer.py re-run against this tokenizer. Do NOT revert to the
    # old AutoTokenizer fallback chain -- that loads the ORIGINAL 32000-vocab
    # tokenizer, which is incompatible with the resized model loaded below
    # and reintroduces the byte-fragmentation bug on Uzbek text.
    from transformers import LlamaTokenizer
    EXTENDED_TOKENIZER_DIR = "/root/aziza-build/model_cache/moshi-extended-model-v2"
    print(f"\n[Model] Loading VOCAB-EXTENDED tokenizer from {EXTENDED_TOKENIZER_DIR} ...")
    tokenizer = LlamaTokenizer.from_pretrained(EXTENDED_TOKENIZER_DIR)
    print(f"[Model] Tokenizer loaded: {len(tokenizer)} tokens (expected 32016)")

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # -- Load base model: VOCAB-EXTENDED Moshi via moshi_resize_utils -------
    # Moshi CANNOT be loaded via AutoModelForCausalLM. It must be loaded
    # through moshi.models.loaders.get_moshi_lm(), THEN resized in-place to
    # match the extended tokenizer (32016 text_emb / 32015 text_linear /
    # 32016 depformer_text_emb rows). load_extended_moshi_lm() does both
    # steps together and loads the already-trained resize weights --
    # do NOT call moshi_loaders.get_moshi_lm() directly here, it returns the
    # ORIGINAL unresized model and will size-mismatch against this tokenizer.
    print("[Model] Loading VOCAB-EXTENDED Moshi LM via moshi_resize_utils ...")
    moshi_loaded = False
    try:
        from moshi_resize_utils import load_extended_moshi_lm
        moshi_lm_raw = load_extended_moshi_lm(device=device)
        moshi_loaded = True
        print("[Model] Vocab-extended Moshi LM loaded successfully.")
        print(f"[Model] text_emb: {moshi_lm_raw.text_emb.weight.shape}, "
              f"text_linear: {moshi_lm_raw.text_linear.weight.shape}")
    except Exception as e:
        print(f"[Warning] Vocab-extended Moshi load failed: {e}")

    if moshi_loaded:
        # --- Wrap the native Moshi LM in a minimal PreTrainedModel shell ---
        # PEFT requires a PreTrainedModel.  We create a thin wrapper that
        # delegates forward() and exposes the correct module tree.
        class _MoshiConfig(PretrainedConfig):
            model_type = "moshi_lm"

        class _MoshiWrapper(PreTrainedModel):
            config_class = _MoshiConfig
            supports_gradient_checkpointing = False

            def __init__(self, inner: nn.Module, vocab_size: int = 32768):
                cfg = _MoshiConfig()
                cfg.vocab_size = vocab_size
                super().__init__(cfg)
                # Register the inner LM as a sub-module so PEFT can walk it.
                self.moshi_lm = inner

            def get_input_embeddings(self):
                # Required by PreTrainedModel; Moshi embeds tokens internally.
                try:
                    return self.moshi_lm.emb
                except AttributeError:
                    return None

            def prepare_inputs_for_generation(self, input_ids, **kwargs):
                # Stub required by PeftModelForCausalLM.__init__.
                # Not used during Trainer-based fine-tuning.
                return {"input_ids": input_ids}

            def forward(
                self,
                input_ids: torch.Tensor,
                labels: torch.Tensor = None,
                attention_mask: torch.Tensor = None,
                **kwargs,
            ):
                # Moshi codebook layout (confirmed by inspection):
                #   num_codebooks=17, audio_offset=1, zero_token_id=-1
                #   codes[:, 0, :]    = TEXT stream  (Helium vocab)
                #   codes[:, 1:17, :] = AUDIO streams (16 audio codebooks)
                #
                # Audio embedding vocab = 2049 (indices 0..2048).
                # Index 2048 is the audio "silence/empty" token used by _get_initial_token().
                # We fill audio slots with 2048 (not 0!) to avoid OOB embedding lookups
                # caused by the delay scheme prepending/shifting initial tokens.
                num_codebooks = self.moshi_lm.num_codebooks   # 17
                audio_offset  = getattr(self.moshi_lm, "audio_offset", 1)  # 1
                audio_card    = getattr(self.moshi_lm, "card", 2048)       # 2048
                text_cb_idx   = audio_offset - 1  # slot 0 = text stream

                if input_ids.dim() == 2:
                    B, T = input_ids.shape
                    # Fill audio slots with audio_card (silence), text slot with actual tokens
                    codes = torch.full((B, num_codebooks, T), audio_card,
                                       dtype=torch.long, device=input_ids.device)
                    codes[:, text_cb_idx, :] = input_ids
                else:
                    codes = input_ids.long()   # already (B, K, T)

                out = self.moshi_lm(codes)

                # LMOutput: .text_logits is the text stream (B, 1, T, text_vocab)
                if hasattr(out, "text_logits") and out.text_logits is not None:
                    logits = out.text_logits.squeeze(1)   # (B, T, text_vocab)
                elif hasattr(out, "logits") and out.logits is not None:
                    logits = out.logits
                else:
                    raise RuntimeError(
                        f"Cannot extract text logits from LMOutput: {type(out)}, "
                        f"attrs={[a for a in dir(out) if not a.startswith('_')]}"
                    )

                loss = None
                if labels is not None:
                    shift_logits = logits[..., :-1, :].contiguous()
                    shift_labels = labels[..., 1:].contiguous()
                    loss = torch.nn.functional.cross_entropy(
                        shift_logits.view(-1, shift_logits.size(-1)),
                        shift_labels.view(-1),
                        ignore_index=-100,
                    )

                from transformers.modeling_outputs import CausalLMOutputWithPast
                return CausalLMOutputWithPast(
                    loss=loss,
                    logits=logits,
                )

        # Move to float16/bfloat16 for memory efficiency
        moshi_lm_raw = moshi_lm_raw.to(torch.bfloat16)
        model = _MoshiWrapper(moshi_lm_raw)
        model.to(device)
        print("[Model] Moshi wrapped in PreTrainedModel shim.")

        # Freeze non-target parameters to simulate QLoRA behaviour
        # (true 4-bit quantisation via bitsandbytes requires AutoModel loading;
        #  here we freeze everything and let PEFT enable only LoRA adapters)
        for param in model.parameters():
            param.requires_grad = False

    else:
        # --- Fallback: load a standard HuggingFace causal LM ---------------
        print(f"[Fallback] Loading {FALLBACK_MODEL_ID} with 4-bit quantisation")
        model = AutoModelForCausalLM.from_pretrained(
            FALLBACK_MODEL_ID,
            quantization_config=BNB_CONFIG,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        )
        model = prepare_model_for_kbit_training(model)
        # For the fallback Mistral model use standard Llama/Mistral target modules
        LORA_CONFIG.target_modules = [
            "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj"
        ]
        print("[Fallback] LoRA target_modules switched to Mistral defaults.")

    # -- Apply LoRA (or resume from existing adapter) ----------------------
    if resume_from and os.path.isdir(resume_from):
        print(f"[LoRA] Loading existing adapter from {resume_from}")
        model = PeftModel.from_pretrained(model, resume_from, is_trainable=True)
    else:
        print("[LoRA] Applying fresh LoRA adapter")
        try:
            model = get_peft_model(model, LORA_CONFIG)
        except ValueError as e:
            print(f"[LoRA Error] {e}")
            print("[LoRA Debug] Available linear modules:")
            for n, m in model.named_modules():
                if isinstance(m, nn.Linear):
                    print(f"  {n}")
            raise

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

