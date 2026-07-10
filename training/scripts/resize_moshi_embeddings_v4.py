#!/usr/bin/env python3
"""
resize_moshi_embeddings_v4.py

Fixed depformer_text_emb initialization — it has dim 1024, not 4096.
Uses moshi.models.loaders.get_moshi_lm() confirmed API.
"""

import os
import torch
import shutil
from huggingface_hub import hf_hub_download

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MOSHI_REPO_ID = "kyutai/moshika-pytorch-bf16"
CACHE_DIR = "/root/aziza-build/model_cache"
TOKENIZER_PATH = os.path.join(CACHE_DIR, "moshi-extended-vocab")
OUTPUT_DIR = os.path.join(CACHE_DIR, "moshi-extended-model")

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
print(f"    Tokenizer vocab_size attr: {tokenizer.vocab_size}")
print(f"    Tokenizer len: {len(tokenizer)}")

for g in UZBEK_GRAPHEMES:
    toks = tokenizer.tokenize(g)
    if len(toks) != 1:
        print(f"    WARNING: '{g}' tokenizes to {toks} (expected 1 token)")
    else:
        tid = tokenizer.convert_tokens_to_ids(toks[0])
        print(f"    '{g}' -> ID {tid}")

# ---------------------------------------------------------------------------
# 2. Load native Moshi model
# ---------------------------------------------------------------------------
print("\n[2/6] Loading native Moshi model via get_moshi_lm...")
from moshi.models import loaders

moshi_weight = hf_hub_download(
    repo_id=MOSHI_REPO_ID,
    filename="model.safetensors",
    cache_dir=CACHE_DIR,
    local_files_only=False
)
print(f"    Checkpoint: {moshi_weight}")

moshi_lm = loaders.get_moshi_lm(moshi_weight, device=DEVICE)
moshi_lm = moshi_lm.to(DTYPE)
moshi_lm.eval()
print(f"    Model loaded on {DEVICE}")
print(f"    Model type: {type(moshi_lm)}")

# ---------------------------------------------------------------------------
# 3. Inspect current embedding shapes
# ---------------------------------------------------------------------------
print("\n[3/6] Inspecting embedding layers...")
text_emb = moshi_lm.text_emb
text_linear = moshi_lm.text_linear

old_text_emb_shape = text_emb.weight.shape
old_text_linear_shape = text_linear.weight.shape

print(f"    text_emb:     {old_text_emb_shape}")
print(f"    text_linear:  {old_text_linear_shape}")
print(f"    text_initial_token_id = {moshi_lm.text_initial_token_id}")
print(f"    text_card = {moshi_lm.text_card}")

# ---------------------------------------------------------------------------
# 4. Compute target sizes
# ---------------------------------------------------------------------------
print("\n[4/6] Computing resize strategy...")

N_REAL_NEW = len(UZBEK_GRAPHEMES)
new_text_emb_rows = old_text_emb_shape[0] + N_REAL_NEW      # 32001 + 15 = 32016
new_text_linear_out = old_text_linear_shape[0] + N_REAL_NEW  # 32000 + 15 = 32015

print(f"    text_emb:    {old_text_emb_shape[0]} -> {new_text_emb_rows}")
print(f"    text_linear: {old_text_linear_shape[0]} -> {new_text_linear_out}")
print(f"    Placeholder at ID 32000 (preserves text_initial_token_id)")
print(f"    Uzbek tokens at IDs 32001 -> {32000 + N_REAL_NEW}")

# ---------------------------------------------------------------------------
# 5. Resize embeddings
# ---------------------------------------------------------------------------
print("\n[5/6] Resizing embeddings...")

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
    vecs = []
    for ch in chars:
        try:
            pieces = tokenizer.tokenize(ch)
            if not pieces:
                continue
            tid = tokenizer.convert_tokens_to_ids(pieces[0])
            if isinstance(tid, list):
                tid = tid[0]
            if tid < emb_weight.shape[0]:
                vecs.append(emb_weight[tid])
        except Exception:
            pass
    if vecs:
        return torch.stack(vecs).mean(dim=0)
    return None

# --- text_emb: (32001, 4096) -> (32016, 4096) ---
old_emb_weight = text_emb.weight.data
new_emb_weight = torch.zeros(new_text_emb_rows, old_emb_weight.shape[1],
                              dtype=old_emb_weight.dtype, device=old_emb_weight.device)
new_emb_weight[:old_emb_weight.shape[0]] = old_emb_weight

for i, grapheme in enumerate(UZBEK_GRAPHEMES):
    new_id = 32001 + i
    similar = SIMILARITY_MAP.get(grapheme, [])
    avg_vec = get_token_avg_embedding(tokenizer, old_emb_weight, similar)
    if avg_vec is not None:
        noise = torch.randn_like(avg_vec) * 0.01
        new_emb_weight[new_id] = avg_vec + noise
        print(f"    ID {new_id:5d} '{grapheme:3s}' <- avg({similar}) + noise")
    else:
        new_emb_weight[new_id] = torch.randn_like(new_emb_weight[new_id]) * 0.001
        print(f"    ID {new_id:5d} '{grapheme:3s}' <- random init")

text_emb.weight = torch.nn.Parameter(new_emb_weight)
print(f"    text_emb -> {text_emb.weight.shape}")

# --- text_linear: (32000, 4096) -> (32015, 4096) ---
old_linear_weight = text_linear.weight.data
old_linear_bias = text_linear.bias.data if text_linear.bias is not None else None

new_linear_weight = torch.zeros(new_text_linear_out, old_linear_weight.shape[1],
                                 dtype=old_linear_weight.dtype, device=old_linear_weight.device)
new_linear_bias = torch.zeros(new_text_linear_out,
                               dtype=old_linear_bias.dtype if old_linear_bias is not None else old_linear_weight.dtype,
                               device=old_linear_weight.device) if old_linear_bias is not None else None

new_linear_weight[:old_linear_weight.shape[0]] = old_linear_weight
if old_linear_bias is not None:
    new_linear_bias[:old_linear_bias.shape[0]] = old_linear_bias

for i, grapheme in enumerate(UZBEK_GRAPHEMES):
    new_out_id = 32000 + i
    similar = SIMILARITY_MAP.get(grapheme, [])
    avg_vec = get_token_avg_embedding(tokenizer, old_linear_weight, similar)
    if avg_vec is not None:
        noise = torch.randn_like(avg_vec) * 0.01
        new_linear_weight[new_out_id] = avg_vec + noise
        if new_linear_bias is not None:
            new_linear_bias[new_out_id] = old_linear_bias.mean()
        print(f"    OUT {new_out_id:5d} '{grapheme:3s}' <- avg({similar}) + noise")
    else:
        new_linear_weight[new_out_id] = torch.randn_like(new_linear_weight[new_out_id]) * 0.001
        if new_linear_bias is not None:
            new_linear_bias[new_out_id] = 0.0
        print(f"    OUT {new_out_id:5d} '{grapheme:3s}' <- random init")

text_linear.in_features = old_linear_weight.shape[1]
text_linear.out_features = new_text_linear_out
text_linear.weight = torch.nn.Parameter(new_linear_weight)
if new_linear_bias is not None:
    text_linear.bias = torch.nn.Parameter(new_linear_bias)
print(f"    text_linear -> {text_linear.weight.shape}")

# --- depformer_text_emb: (32001, 1024) -> (32016, 1024) ---
if hasattr(moshi_lm, 'depformer_text_emb') and moshi_lm.depformer_text_emb is not None:
    dep_emb = moshi_lm.depformer_text_emb
    old_dep_shape = dep_emb.weight.shape
    new_dep_weight = torch.zeros(new_text_emb_rows, old_dep_shape[1],
                                  dtype=dep_emb.weight.dtype, device=dep_emb.weight.device)
    new_dep_weight[:old_dep_shape[0]] = dep_emb.weight.data

    # Initialize depformer new rows using depformer's OWN embeddings for similar chars
    for i, grapheme in enumerate(UZBEK_GRAPHEMES):
        new_id = 32001 + i
        similar = SIMILARITY_MAP.get(grapheme, [])
        avg_vec = get_token_avg_embedding(tokenizer, dep_emb.weight.data, similar)
        if avg_vec is not None:
            noise = torch.randn_like(avg_vec) * 0.01
            new_dep_weight[new_id] = avg_vec + noise
        else:
            new_dep_weight[new_id] = torch.randn_like(new_dep_weight[new_id]) * 0.001

    dep_emb.weight = torch.nn.Parameter(new_dep_weight)
    print(f"    depformer_text_emb -> {dep_emb.weight.shape}")

# ---------------------------------------------------------------------------
# 6. Save
# ---------------------------------------------------------------------------
print("\n[6/6] Saving modified checkpoint...")
os.makedirs(OUTPUT_DIR, exist_ok=True)

torch.save(moshi_lm.state_dict(), os.path.join(OUTPUT_DIR, "model.pt"))
print(f"    Saved: {os.path.join(OUTPUT_DIR, 'model.pt')}")

if os.path.exists(TOKENIZER_PATH):
    for f in os.listdir(TOKENIZER_PATH):
        src = os.path.join(TOKENIZER_PATH, f)
        dst = os.path.join(OUTPUT_DIR, f)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
    print(f"    Copied tokenizer files")

with open(os.path.join(OUTPUT_DIR, "resize_metadata.txt"), "w") as f:
    f.write(f"Original text_emb rows: {old_text_emb_shape[0]}\n")
    f.write(f"New text_emb rows: {new_text_emb_rows}\n")
    f.write(f"Original text_linear out: {old_text_linear_shape[0]}\n")
    f.write(f"New text_linear out: {new_text_linear_out}\n")
    f.write(f"Placeholder at ID 32000 (text_initial_token_id)\n")
    f.write(f"Uzbek graphemes at IDs: 32001 - {32000 + N_REAL_NEW}\n")

print(f"    Saved metadata")
print("\n" + "="*60)
print("RESIZE COMPLETE")
print("="*60)
print(f"Output: {OUTPUT_DIR}")
