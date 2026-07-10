#!/usr/bin/env python3
"""
fix_tokenizer_offset.py

The model embeddings were resized with:
  - ID 32000 = reserved (text_initial_token_id, preserved from original)
  - IDs 32001-32015 = Uzbek graphemes

But the current tokenizer has Uzbek graphemes at IDs 32000-32014.
This script fixes the tokenizer by:
  1. Loading the ORIGINAL Moshi SPM (before any extension)
  2. Adding 1 placeholder token FIRST (consumes ID 32000)
  3. Adding all 15 Uzbek graphemes SECOND (get IDs 32001-32015)
  4. Saving the corrected tokenizer
"""

import os
import shutil
from pathlib import Path

TOKENIZER_PATH = "/root/aziza-build/model_cache/moshi-extended-vocab"
OUTPUT_PATH = "/root/aziza-build/model_cache/moshi-extended-vocab-fixed"

UZBEK_GRAPHEMES = [
    "Oʻ", "oʻ", "Gʻ", "gʻ", "ʻ",
    "Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў",
]

os.makedirs(OUTPUT_PATH, exist_ok=True)

# ---------------------------------------------------------------------------
# Step 1: Find the original Moshi SPM file
# ---------------------------------------------------------------------------
print("[1/4] Locating original Moshi SPM...")

original_model_file = None
# Search in HF cache for the original tokenizer_spm_32k_3.model
for root, dirs, files in os.walk("/root/aziza-build/model_cache"):
    for f in files:
        if f == "tokenizer_spm_32k_3.model":
            original_model_file = os.path.join(root, f)
            break
    if original_model_file:
        break

if not original_model_file:
    # Fallback: check if there's a tokenizer.model in the current extended vocab
    fallback = os.path.join(TOKENIZER_PATH, "tokenizer.model")
    if os.path.exists(fallback):
        original_model_file = fallback
        print(f"    Using fallback: {original_model_file}")
    else:
        raise FileNotFoundError(
            "Cannot find original tokenizer_spm_32k_3.model or tokenizer.model. "
            "Please ensure the original Moshi tokenizer is cached."
        )
else:
    print(f"    Found original SPM: {original_model_file}")

# ---------------------------------------------------------------------------
# Step 2: Load original tokenizer
# ---------------------------------------------------------------------------
print("\n[2/4] Loading original tokenizer...")
from transformers import LlamaTokenizer

tokenizer = LlamaTokenizer(vocab_file=original_model_file)
print(f"    Base vocab size: {tokenizer.vocab_size}")
print(f"    Base len: {len(tokenizer)}")

# Verify base tokenizer doesn't have Uzbek tokens yet
for g in UZBEK_GRAPHEMES[:3]:
    toks = tokenizer.tokenize(g)
    print(f"    '{g}' -> {toks} (len={len(toks)})")

# ---------------------------------------------------------------------------
# Step 3: Add tokens in CORRECT order
# ---------------------------------------------------------------------------
print("\n[3/4] Adding tokens in correct order...")

# CRITICAL: Add placeholder FIRST so it gets ID 32000
placeholder_token = "<reserved_text_initial_32000>"
added = tokenizer.add_tokens([placeholder_token])
print(f"    Added placeholder '{placeholder_token}': +{added} token(s)")
print(f"    Vocab after placeholder: {len(tokenizer)}")

# Now add Uzbek graphemes — they will get IDs 32001-32015
added = tokenizer.add_tokens(UZBEK_GRAPHEMES)
print(f"    Added {added} Uzbek graphemes")
print(f"    Final vocab size: {len(tokenizer)}")

# Verify correct IDs
print("\n    Verifying corrected token IDs:")
placeholder_id = tokenizer.convert_tokens_to_ids(placeholder_token)
print(f"    Placeholder '{placeholder_token}' -> ID {placeholder_id}")

for g in UZBEK_GRAPHEMES:
    toks = tokenizer.tokenize(g)
    tid = tokenizer.convert_tokens_to_ids(toks[0])
    print(f"    '{g}' -> ID {tid}")

# Sanity check
assert placeholder_id == 32000, f"Placeholder should be at 32000, got {placeholder_id}"
first_uzbek_id = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(UZBEK_GRAPHEMES[0])[0])
assert first_uzbek_id == 32001, f"First Uzbek should be at 32001, got {first_uzbek_id}"
last_uzbek_id = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(UZBEK_GRAPHEMES[-1])[0])
assert last_uzbek_id == 32015, f"Last Uzbek should be at 32015, got {last_uzbek_id}"
print("\n    ✓ All ID assertions passed!")

# ---------------------------------------------------------------------------
# Step 4: Save corrected tokenizer
# ---------------------------------------------------------------------------
print("\n[4/4] Saving corrected tokenizer...")

tokenizer.save_pretrained(OUTPUT_PATH)

# Also copy the SPM .model file
shutil.copy2(original_model_file, os.path.join(OUTPUT_PATH, "tokenizer.model"))

# Save metadata
with open(os.path.join(OUTPUT_PATH, "tokenizer_fix_metadata.txt"), "w") as f:
    f.write("Tokenizer offset fix applied\n")
    f.write("="*50 + "\n")
    f.write(f"Original vocab size: 32000\n")
    f.write(f"Placeholder token: {placeholder_token} at ID {placeholder_id}\n")
    f.write(f"Uzbek graphemes at IDs: 32001 - 32015\n")
    f.write(f"Final vocab size: {len(tokenizer)}\n")
    f.write("\nToken mapping:\n")
    f.write(f"  {placeholder_token} -> {placeholder_id}\n")
    for g in UZBEK_GRAPHEMES:
        tid = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(g)[0])
        f.write(f"  {g} -> {tid}\n")

print(f"    Saved tokenizer to: {OUTPUT_PATH}")
print(f"    Saved metadata")

print("\n" + "="*60)
print("TOKENIZER OFFSET FIX COMPLETE")
print("="*60)
print(f"\nNext steps:")
print(f"  1. Update finetune_moshi.py to load tokenizer from: {OUTPUT_PATH}")
print(f"  2. Update finetune_moshi.py to load model from: /root/aziza-build/model_cache/moshi-extended-model")
print(f"  3. Verify get_input_embeddings() returns text_emb, not moshi_lm.emb")
print(f"  4. Run training — tokenizer IDs now match model embedding rows")
