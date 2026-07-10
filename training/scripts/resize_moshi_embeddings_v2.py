#!/usr/bin/env python3
"""
resize_moshi_embeddings.py

Correctly resizes Moshi's text embeddings after tokenizer vocab extension.
Uses the actual moshi package API (not AutoModelForCausalLM).

CRITICAL OFFSET FIX:
- text_emb has 32001 rows (0-32000). Index 32000 = text_initial_token_id.
- text_linear has 32000 outputs (0-31999). It never predicts index 32000.
- We insert 1 PLACEHOLDER token first to consume ID 32000, preserving the
  special text_initial_token_id slot.
- Then we add the 15 real Uzbek graphemes at IDs 32001-32015.
- Final sizes: text_emb = 32017, text_linear = 32015.
"""

import os
import sys
import torch
import shutil
from pathlib import Path
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MOSHI_REPO_ID = "kyutai/moshika-pytorch-bf16"
CACHE_DIR = "/root/aziza-build/model_cache"
TOKENIZER_PATH = os.path.join(CACHE_DIR, "moshi-extended-vocab")
OUTPUT_DIR = os.path.join(CACHE_DIR, "moshi-extended-model")

# The 15 Uzbek graphemes that were added to the tokenizer
UZBEK_GRAPHEMES = [
    "Oʻ", "oʻ", "Gʻ", "gʻ", "ʻ",
    "Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў",
]

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16

# ---------------------------------------------------------------------------
# 1. Load extended tokenizer
# ---------------------------------------------------------------------------
print("[1/6] Loading extended tokenizer...")
from transformers import LlamaTokenizer

tokenizer = LlamaTokenizer.from_pretrained(TOKENIZER_PATH)
vocab_size = tokenizer.vocab_size
print(f"    Tokenizer vocab size: {vocab_size}")

# Verify our graphemes are single tokens
for g in UZBEK_GRAPHEMES:
    toks = tokenizer.tokenize(g)
    if len(toks) != 1:
        print(f"    WARNING: '{g}' tokenizes to {toks} (expected 1 token)")
    else:
        tid = tokenizer.convert_tokens_to_ids(toks[0])
        print(f"    '{g}' -> ID {tid}")

# ---------------------------------------------------------------------------
# 2. Load native Moshi model using the actual moshi package API
# ---------------------------------------------------------------------------
print("\n[2/6] Loading native Moshi model...")
from moshi.models import loaders, lm

# Download / locate checkpoint using the official API
moshi_weight = hf_hub_download(MOSHI_REPO_ID, "model.safetensors", cache_dir=CACHE_DIR)
print(f"    Checkpoint: {moshi_weight}")

# Load state dict from safetensors
print("    Loading state dict from safetensors...")
state_dict = load_file(moshi_weight, device=DEVICE)
print(f"    Loaded {len(state_dict)} tensors")

# Build the model architecture from config
# Based on moshi source: text_card=32000, existing_text_padding_id=3
model_cfg = {
    "text_card": 32000,
    "existing_text_padding_id": 3,
}
print(f"    Building MoshiLM with config: {model_cfg}")
moshi_lm = lm.MoshiLM(**model_cfg)

# Load weights
missing, unexpected = moshi_lm.load_state_dict(state_dict, strict=False)
if missing:
    print(f"    Missing keys: {missing}")
if unexpected:
    print(f"    Unexpected keys: {unexpected}")

moshi_lm = moshi_lm.to(DEVICE).to(DTYPE)
moshi_lm.eval()
print(f"    Model loaded on {DEVICE}")

# ---------------------------------------------------------------------------
# 3. Inspect current embedding shapes
# ---------------------------------------------------------------------------
print("\n[3/6] Inspecting embedding layers...")
text_emb = moshi_lm.text_emb
text_linear = moshi_lm.text_linear

old_text_emb_shape = text_emb.weight.shape  # (32001, 4096)
old_text_linear_shape = text_linear.weight.shape  # (32000, 4096)

print(f"    text_emb:     {old_text_emb_shape}")
print(f"    text_linear:  {old_text_linear_shape}")
print(f"    text_initial_token_id = {moshi_lm.text_initial_token_id}")
print(f"    text_card = {moshi_lm.text_card}")

# ---------------------------------------------------------------------------
# 4. Compute target sizes with offset fix
# ---------------------------------------------------------------------------
print("\n[4/6] Computing resize strategy...")

# We need to add 1 placeholder + 15 real tokens = 16 total new rows for text_emb
# text_linear only needs the 15 real tokens (it never had the special row)
N_PLACEHOLDER = 1
N_REAL_NEW = len(UZBEK_GRAPHEMES)
N_TOTAL_NEW_EMB = N_PLACEHOLDER + N_REAL_NEW  # 16

new_text_emb_rows = old_text_emb_shape[0] + N_TOTAL_NEW_EMB      # 32001 + 16 = 32017
new_text_linear_out = old_text_linear_shape[0] + N_REAL_NEW       # 32000 + 15 = 32015

print(f"    text_emb will grow:    {old_text_emb_shape[0]} -> {new_text_emb_rows}")
print(f"    text_linear will grow: {old_text_linear_shape[0]} -> {new_text_linear_out}")
print(f"    Placeholder token at ID {old_text_emb_shape[0]} (preserves text_initial_token_id)")
print(f"    Real Uzbek tokens at IDs {old_text_emb_shape[0] + 1} -> {old_text_emb_shape[0] + N_REAL_NEW}")

# ---------------------------------------------------------------------------
# 5. Resize embeddings with smart initialization
# ---------------------------------------------------------------------------
print("\n[5/6] Resizing embeddings...")

# --- text_emb: ScaledEmbedding(32001, 4096) -> ScaledEmbedding(32017, 4096) ---
old_emb_weight = text_emb.weight.data  # (32001, 4096)
new_emb_weight = torch.zeros(new_text_emb_rows, old_emb_weight.shape[1],
                              dtype=old_emb_weight.dtype, device=old_emb_weight.device)

# Copy original weights
new_emb_weight[:old_emb_weight.shape[0]] = old_emb_weight

# Row 32000 (the special text_initial_token_id) stays exactly as-is — we copied it
# Row 32001-32016: initialize new Uzbek tokens

# Strategy: average embeddings of visually/phonetically similar existing tokens
# For Latin Oʻ/oʻ/Gʻ/gʻ/ʻ -> average of base Latin chars (O, o, G, g, apostrophe-like)
# For Cyrillic -> average of similar Cyrillic chars
SIMILARITY_MAP = {
    "Oʻ": ["O", "o", "'", "`"],
    "oʻ": ["o", "O", "'", "`"],
    "Gʻ": ["G", "g", "'", "`"],
    "gʻ": ["g", "G", "'", "`"],
    "ʻ":  ["'", "`", "\u2019", "\u2018"],
    "Ҳ":  ["Х", "х", "H"],
    "ҳ":  ["х", "Х", "h"],
    "Ҷ":  ["Ч", "ч", "J"],
    "ҷ":  ["ч", "Ч", "j"],
    "Қ":  ["К", "к", "Q"],
    "қ":  ["к", "К", "q"],
    "Ғ":  ["Г", "г", "G"],
    "ғ":  ["г", "Г", "g"],
    "Ў":  ["У", "у", "O"],
    "ў":  ["у", "У", "o"],
}

def get_token_avg_embedding(tokenizer, emb_weight, chars):
    """Average embeddings for a list of characters/tokens."""
    vecs = []
    for ch in chars:
        try:
            tid = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(ch))
            if isinstance(tid, list):
                tid = tid[0]
            if tid < emb_weight.shape[0]:
                vecs.append(emb_weight[tid])
        except Exception:
            pass
    if vecs:
        return torch.stack(vecs).mean(dim=0)
    return None

# Placeholder at 32000: clone the special initial token row (already copied, but mark it)
# We leave it untouched — it's the same semantic token it always was.

# Initialize real new tokens at 32001+
for i, grapheme in enumerate(UZBEK_GRAPHEMES):
    new_id = old_emb_weight.shape[0] + 1 + i  # 32001, 32002, ...
    similar = SIMILARITY_MAP.get(grapheme, [])
    avg_vec = get_token_avg_embedding(tokenizer, old_emb_weight, similar)

    if avg_vec is not None:
        # Add small Gaussian noise to break symmetry during training
        noise = torch.randn_like(avg_vec) * 0.01
        new_emb_weight[new_id] = avg_vec + noise
        print(f"    ID {new_id:5d} '{grapheme:3s}' <- avg({similar}) + noise")
    else:
        # Fallback: zero-init with small noise
        new_emb_weight[new_id] = torch.randn_like(new_emb_weight[new_id]) * 0.001
        print(f"    ID {new_id:5d} '{grapheme:3s}' <- random init (fallback)")

# Apply new weight to text_emb
text_emb.weight = torch.nn.Parameter(new_emb_weight)
print(f"    text_emb resized to: {text_emb.weight.shape}")

# --- text_linear: Linear(4096, 32000) -> Linear(4096, 32015) ---
old_linear_weight = text_linear.weight.data  # (32000, 4096)
old_linear_bias = text_linear.bias.data if text_linear.bias is not None else None

new_linear_weight = torch.zeros(new_text_linear_out, old_linear_weight.shape[1],
                                 dtype=old_linear_weight.dtype, device=old_linear_weight.device)
new_linear_bias = torch.zeros(new_text_linear_out,
                               dtype=old_linear_bias.dtype if old_linear_bias is not None else old_linear_weight.dtype,
                               device=old_linear_weight.device) if old_linear_bias is not None else None

# Copy original weights (IDs 0-31999)
new_linear_weight[:old_linear_weight.shape[0]] = old_linear_weight
if old_linear_bias is not None:
    new_linear_bias[:old_linear_bias.shape[0]] = old_linear_bias

# Initialize new output rows (IDs 32000-32014) by averaging similar token output weights
for i, grapheme in enumerate(UZBEK_GRAPHEMES):
    new_out_id = old_linear_weight.shape[0] + i  # 32000, 32001, ...
    similar = SIMILARITY_MAP.get(grapheme, [])
    avg_vec = get_token_avg_embedding(tokenizer, old_linear_weight, similar)

    if avg_vec is not None:
        noise = torch.randn_like(avg_vec) * 0.01
        new_linear_weight[new_out_id] = avg_vec + noise
        if new_linear_bias is not None:
            new_linear_bias[new_out_id] = old_linear_bias[:old_linear_weight.shape[0]].mean() if old_linear_bias is not None else 0.0
        print(f"    OUT {new_out_id:5d} '{grapheme:3s}' <- avg({similar}) + noise")
    else:
        new_linear_weight[new_out_id] = torch.randn_like(new_linear_weight[new_out_id]) * 0.001
        if new_linear_bias is not None:
            new_linear_bias[new_out_id] = 0.0
        print(f"    OUT {new_out_id:5d} '{grapheme:3s}' <- random init (fallback)")

# Reconstruct the Linear layer
text_linear.in_features = old_linear_weight.shape[1]
text_linear.out_features = new_text_linear_out
text_linear.weight = torch.nn.Parameter(new_linear_weight)
if new_linear_bias is not None:
    text_linear.bias = torch.nn.Parameter(new_linear_bias)
print(f"    text_linear resized to: {text_linear.weight.shape}")

# --- depformer_text_emb also needs resizing (32001 -> 32017) ---
if hasattr(moshi_lm, 'depformer_text_emb') and moshi_lm.depformer_text_emb is not None:
    dep_emb = moshi_lm.depformer_text_emb
    old_dep_shape = dep_emb.weight.shape
    new_dep_weight = torch.zeros(new_text_emb_rows, old_dep_shape[1],
                                  dtype=dep_emb.weight.dtype, device=dep_emb.weight.device)
    new_dep_weight[:old_dep_shape[0]] = dep_emb.weight.data
    # Copy same init strategy as text_emb for new rows
    for i, grapheme in enumerate(UZBEK_GRAPHEMES):
        new_id = old_emb_weight.shape[0] + 1 + i
        new_dep_weight[new_id] = new_emb_weight[new_id]  # copy from text_emb (same semantic init)
    dep_emb.weight = torch.nn.Parameter(new_dep_weight)
    print(f"    depformer_text_emb resized to: {dep_emb.weight.shape}")

# ---------------------------------------------------------------------------
# 6. Save modified checkpoint
# ---------------------------------------------------------------------------
print("\n[6/6] Saving modified checkpoint...")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Save model state dict
torch.save(moshi_lm.state_dict(), os.path.join(OUTPUT_DIR, "model.pt"))
print(f"    Saved: {os.path.join(OUTPUT_DIR, 'model.pt')}")

# Copy tokenizer files
if os.path.exists(TOKENIZER_PATH):
    for f in os.listdir(TOKENIZER_PATH):
        src = os.path.join(TOKENIZER_PATH, f)
        dst = os.path.join(OUTPUT_DIR, f)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
    print(f"    Copied tokenizer files to {OUTPUT_DIR}")

# Save a config/metadata file
with open(os.path.join(OUTPUT_DIR, "resize_metadata.txt"), "w") as f:
    f.write(f"Original text_emb rows: {old_text_emb_shape[0]}\n")
    f.write(f"New text_emb rows: {new_text_emb_rows}\n")
    f.write(f"Original text_linear out: {old_text_linear_shape[0]}\n")
    f.write(f"New text_linear out: {new_text_linear_out}\n")
    f.write(f"Placeholder token at ID: {old_text_emb_shape[0]}\n")
    f.write(f"Uzbek graphemes at IDs: {old_text_emb_shape[0] + 1} - {old_text_emb_shape[0] + N_REAL_NEW}\n")
    f.write(f"text_initial_token_id preserved at: {moshi_lm.text_initial_token_id}\n")
    f.write(f"New tokens: {UZBEK_GRAPHEMES}\n")

print(f"    Saved: {os.path.join(OUTPUT_DIR, 'resize_metadata.txt')}")

print("\n" + "="*60)
print("RESIZE COMPLETE")
print("="*60)
print(f"Output directory: {OUTPUT_DIR}")
print(f"\nNext steps:")
print(f"  1. Update finetune_moshi.py to load from: {OUTPUT_DIR}")
print(f"  2. Ensure get_input_embeddings() returns text_emb, not moshi_lm.emb")
print(f"  3. Verify tokenizer model uses the extended vocab")
print(f"  4. Run training — new tokens are initialized close to similar chars")
