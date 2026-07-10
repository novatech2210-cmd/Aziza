"""
find_text_embedding.py

Confirmed: moshi_lm.emb is the AUDIO codebook embedding (16x ScaledEmbedding(2049, 4096)),
NOT the text embedding. The _MoshiWrapper.get_input_embeddings() in finetune_moshi.py is
pointing at the wrong module.

This script walks every named module in the loaded Moshi LM and prints any
embedding/linear layer whose size is in the neighborhood of the TEXT vocab
(32000 tokenizer pieces, or 32768 as hinted by the wrapper's default vocab_size),
so we can find the real text embedding + output projection to resize correctly.
"""

from huggingface_hub import hf_hub_download
from moshi.models import loaders as moshi_loaders
import torch.nn as nn

BASE_MODEL_ID = "kyutai/moshika-pytorch-bf16"

print(f"Loading native Moshi LM from {BASE_MODEL_ID} ...")
weight_path = hf_hub_download(BASE_MODEL_ID, filename="model.safetensors")
moshi_lm = moshi_loaders.get_moshi_lm(weight_path, device="cpu")

print("\n--- Top-level attributes on moshi_lm ---")
for name, _ in moshi_lm.named_children():
    print(f"  {name}")

print("\n--- All Embedding / Linear layers, filtered near text-vocab size ---")
TEXT_VOCAB_CANDIDATES_MIN = 30000
TEXT_VOCAB_CANDIDATES_MAX = 40000

for name, module in moshi_lm.named_modules():
    # Embedding layers
    if isinstance(module, nn.Embedding) or module.__class__.__name__ in ("Embedding", "ScaledEmbedding"):
        try:
            num_emb = getattr(module, "num_embeddings", None)
            dim = getattr(module, "embedding_dim", None)
            if num_emb and TEXT_VOCAB_CANDIDATES_MIN <= num_emb <= TEXT_VOCAB_CANDIDATES_MAX:
                print(f"  [EMBED CANDIDATE] {name}: {module.__class__.__name__}({num_emb}, {dim})")
            else:
                print(f"  [embedding, not text-sized] {name}: {module.__class__.__name__}({num_emb}, {dim})")
        except Exception as e:
            print(f"  [error inspecting {name}]: {e}")

    # Linear layers (potential output head / lm_head projecting to vocab size)
    if isinstance(module, nn.Linear) or module.__class__.__name__ in ("Linear",):
        try:
            out_features = getattr(module, "out_features", None)
            in_features = getattr(module, "in_features", None)
            if out_features and TEXT_VOCAB_CANDIDATES_MIN <= out_features <= TEXT_VOCAB_CANDIDATES_MAX:
                print(f"  [LM HEAD CANDIDATE] {name}: Linear({in_features}, {out_features})")
        except Exception as e:
            print(f"  [error inspecting {name}]: {e}")

print("\n--- Full module tree (names only, for reference) ---")
for name, module in moshi_lm.named_modules():
    if name:  # skip root
        depth = name.count(".")
        if depth <= 2:  # keep it readable
            print(f"  {'  ' * depth}{name}: {module.__class__.__name__}")
