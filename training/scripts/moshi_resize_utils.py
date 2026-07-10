"""
moshi_resize_utils.py

Confirmed-working resize functions extracted from resize_and_validate_moshi.py.
Import these into finetune_moshi.py so training always loads the model the
same, correct way -- text_emb/text_linear/depformer_text_emb resized to match
the extended tokenizer, IDs 32001-32015 for the 15 new Uzbek/Cyrillic
graphemes, ID 32000 preserved as the model's original special token.
"""

import json
import torch
import torch.nn as nn
from pathlib import Path
from huggingface_hub import hf_hub_download
from moshi.models import loaders as moshi_loaders

BASE_MODEL_ID = "kyutai/moshika-pytorch-bf16"
RESIZE_DIR = Path("/root/aziza-build/model_cache/moshi-extended-model-v2")

# Confirmed working in production run: matches real module names
# (in_projs.0, out_projs.0, ... inside indexed ModuleLists), NOT 'in_proj'/'out_proj'.
LORA_TARGET_MODULES_REGEX = r".*\.(in_projs|out_projs)\.\d+$"


def resize_weight_matrix(old_weight: torch.Tensor, new_rows: int, seed_scale: float = 0.02) -> torch.Tensor:
    old_rows, dim = old_weight.shape
    assert new_rows >= old_rows
    new_weight = torch.zeros(new_rows, dim, dtype=old_weight.dtype, device=old_weight.device)
    new_weight[:old_rows] = old_weight
    if new_rows > old_rows:
        mean = old_weight.mean(dim=0)
        std = old_weight.float().std(dim=0).to(old_weight.dtype)
        noise = torch.randn(new_rows - old_rows, dim, dtype=old_weight.dtype, device=old_weight.device)
        new_weight[old_rows:] = mean + noise * std * seed_scale
    return new_weight


def resize_embedding_inplace(module: nn.Module, new_num_embeddings: int):
    new_weight = resize_weight_matrix(module.weight.data, new_num_embeddings)
    module.weight = nn.Parameter(new_weight)
    if hasattr(module, "num_embeddings"):
        module.num_embeddings = new_num_embeddings


def resize_linear_output_inplace(module: nn.Linear, new_out_features: int):
    new_weight = resize_weight_matrix(module.weight.data, new_out_features)
    module.weight = nn.Parameter(new_weight)
    module.out_features = new_out_features
    if module.bias is not None:
        old_bias = module.bias.data
        new_bias = torch.zeros(new_out_features, dtype=old_bias.dtype, device=old_bias.device)
        new_bias[: old_bias.shape[0]] = old_bias
        module.bias = nn.Parameter(new_bias)


def load_extended_moshi_lm(device: str = "cuda") -> nn.Module:
    """The ONE correct way to load the vocab-extended Moshi model for training
    or inference. Re-applies the exact resize used when the checkpoint was
    built, then loads the saved state_dict with strict=True (shapes will
    match -- if they don't, resize_metadata.json is stale and needs
    regenerating via resize_and_validate_moshi.py)."""
    with open(RESIZE_DIR / "resize_metadata.json") as f:
        meta = json.load(f)

    weight_path = hf_hub_download(BASE_MODEL_ID, filename="model.safetensors")
    model = moshi_loaders.get_moshi_lm(weight_path, device=device)

    resize_embedding_inplace(model.text_emb, meta["target_text_emb"])
    resize_linear_output_inplace(model.text_linear, meta["target_text_linear"])
    resize_embedding_inplace(model.depformer_text_emb, meta["target_depformer_text_emb"])

    state_dict = torch.load(RESIZE_DIR / "model_state_dict.pt", map_location=device, weights_only=True)
    model.load_state_dict(state_dict, strict=True)

    return model
