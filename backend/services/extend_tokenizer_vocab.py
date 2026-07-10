"""
extend_tokenizer_vocab.py

Fixes the confirmed tokenizer fragmentation bug: Moshi's native 32k SentencePiece
vocab has NO tokens for Uzbek Latin okina (ʻ) or Uzbek/Cyrillic-specific letters
(Ҳ ҳ Ҷ ҷ Қ қ Ғ ғ Ў ў). These currently fall back to 2-3 raw UTF-8 byte tokens
each, confirmed via audit_tokenizer.py output on 2026-07-07.

This script:
1. Loads the native LlamaTokenizer wrapping Moshi's SentencePiece model
2. Adds the missing graphemes as new tokens (as whole characters, so they get
   single token IDs instead of byte-fallback fragments)
3. Saves the extended tokenizer
4. Loads the base Moshi model and resizes its input/output embedding matrices
   to match the new vocab size (new rows get randomly initialized -- these
   will be learned during LoRA/base fine-tuning, NOT frozen)
5. Saves the resized base model checkpoint

Run this ONCE before any further training. All existing LoRA adapters
(ru_all, ru_colloquial, or anything in this client package) were trained
against the OLD vocab size and are NOT compatible with the extended model --
they must be retrained from this new base.

Usage:
    python3 extend_tokenizer_vocab.py
"""

import os
from transformers import LlamaTokenizer, AutoModelForCausalLM
from huggingface_hub import hf_hub_download

MOSHI_REPO_ID = "kyutai/moshika-pytorch-bf16"
OUTPUT_DIR = "/root/aziza-build/model_cache/moshi-extended-vocab"

# Confirmed missing graphemes from audit_tokenizer.py output (2026-07-07).
# Every one of these currently fragments into 2-3 raw byte tokens.
MISSING_GRAPHEMES = [
    "Oʻ", "oʻ", "Gʻ", "gʻ",   # Uzbek Latin (also add bare ʻ itself)
    "ʻ",
    "Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў",  # Uzbek/Cyrillic
]


def main():
    print(f"[1/5] Loading native SentencePiece tokenizer from {MOSHI_REPO_ID} ...")
    model_path = hf_hub_download(repo_id=MOSHI_REPO_ID, filename="tokenizer_spm_32k_3.model")
    tokenizer = LlamaTokenizer(vocab_file=model_path)
    original_vocab_size = tokenizer.vocab_size
    print(f"    Original vocab size: {original_vocab_size}")

    print(f"\n[2/5] Checking fragmentation before fix...")
    for g in MISSING_GRAPHEMES:
        pieces = tokenizer.tokenize(g)
        print(f"    '{g}' -> {pieces} (len={len(pieces)})")

    print(f"\n[3/5] Adding {len(MISSING_GRAPHEMES)} missing graphemes as new tokens...")
    num_added = tokenizer.add_tokens(MISSING_GRAPHEMES)
    new_vocab_size = len(tokenizer)
    print(f"    Added {num_added} new tokens. New vocab size: {new_vocab_size}")

    print(f"\n[4/5] Verifying fragmentation after fix...")
    all_single_token = True
    for g in MISSING_GRAPHEMES:
        pieces = tokenizer.tokenize(g)
        status = "OK" if len(pieces) == 1 else "STILL FRAGMENTED"
        if len(pieces) != 1:
            all_single_token = False
        print(f"    '{g}' -> {pieces} (len={len(pieces)}) [{status}]")

    if not all_single_token:
        print("\n[WARNING] Some graphemes still fragmented after adding tokens.")
        print("This can happen with SentencePiece's normalization -- check NFC/NFKC")
        print("normalization settings before proceeding to model resize.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"\n    Extended tokenizer saved to {OUTPUT_DIR}")

    print(f"\n[5/5] Loading base model and resizing embeddings ({original_vocab_size} -> {new_vocab_size}) ...")
    model = AutoModelForCausalLM.from_pretrained(MOSHI_REPO_ID, torch_dtype="bfloat16")
    model.resize_token_embeddings(new_vocab_size)
    model.save_pretrained(OUTPUT_DIR)
    print(f"    Resized base model saved to {OUTPUT_DIR}")

    print("\n" + "=" * 70)
    print("DONE. Next steps:")
    print(f"  1. Update finetune_moshi.py TOKENIZER_ID / MODEL_ID to point at:")
    print(f"     {OUTPUT_DIR}")
    print(f"  2. Re-run training from this new base -- ALL prior adapters")
    print(f"     (ru_all, ru_colloquial, anything from the client zip) are")
    print(f"     incompatible with the new vocab size and must be retrained.")
    print(f"  3. Re-run audit_tokenizer.py against the new tokenizer to confirm")
    print(f"     zero fragmentation before starting the real training run.")
    print("=" * 70)


if __name__ == "__main__":
    main()
