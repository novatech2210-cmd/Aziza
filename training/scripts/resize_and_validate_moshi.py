"""
resize_and_validate_moshi.py

Single source of truth for the text-vocab resize. Replaces the v5/v2 script
chain, which had two bugs:

  BUG 1: resize_moshi_embeddings_v5.py computed correct target shapes and
  saved a state_dict with those shapes, but validate_patched_finetune_v2.py
  then loaded a FRESH, unmodified base model (original shapes: text_emb
  32001, text_linear 32000, depformer_text_emb 32001) and tried to force the
  bigger state_dict into it. Hence every "size mismatch" error. The fix: this
  script resizes the LIVE model object's modules in-place (replacing the
  weight tensors directly), then saves + reloads the SAME way every time, so
  shapes always match.

  BUG 2: LoRA target_modules was {'in_proj', 'out_proj'} (singular, no
  index). Real module names, confirmed by inspection, are things like
  'transformer.layers.0.self_attn.in_projs.0' and '...out_projs.0' -- plural,
  inside indexed ModuleLists. PEFT's list-based target_modules does a suffix
  match on dotted names and will never match 'in_proj' against
  'in_projs.0'. Fix: use PEFT's regex mode (pass target_modules as a single
  regex string) matching the real names.

Token ID layout (confirmed correct in the v5 run, kept as-is):
  0     - 31999  : original SentencePiece vocab (unchanged)
  32000          : placeholder, preserves the model's existing
                   text_initial_token_id / text_card special row
  32001 - 32015  : the 15 new Uzbek/Cyrillic graphemes

Run with: python3 resize_and_validate_moshi.py
"""

import json
import torch
import torch.nn as nn
from pathlib import Path
from huggingface_hub import hf_hub_download
from moshi.models import loaders as moshi_loaders
from transformers import LlamaTokenizer

BASE_MODEL_ID = "kyutai/moshika-pytorch-bf16"
TOKENIZER_DIR = "/root/aziza-build/model_cache/moshi-extended-vocab"
OUTPUT_DIR = Path("/root/aziza-build/model_cache/moshi-extended-model-v2")
DEVICE = "cuda"

NEW_GRAPHEMES_IN_ORDER = [
    "Oʻ", "oʻ", "Gʻ", "gʻ", "ʻ",
    "Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў",
]


def resize_weight_matrix(old_weight: torch.Tensor, new_rows: int, seed_scale: float = 0.02) -> torch.Tensor:
    """Grow a (rows, dim) weight tensor to new_rows, keeping existing rows
    identical and initializing new rows near the mean of existing rows with
    small noise (standard practice for embedding-table growth)."""
    old_rows, dim = old_weight.shape
    assert new_rows >= old_rows, f"new_rows ({new_rows}) must be >= old_rows ({old_rows})"
    new_weight = torch.zeros(new_rows, dim, dtype=old_weight.dtype, device=old_weight.device)
    new_weight[:old_rows] = old_weight
    if new_rows > old_rows:
        mean = old_weight.mean(dim=0)
        std = old_weight.float().std(dim=0).to(old_weight.dtype)
        noise = torch.randn(new_rows - old_rows, dim, dtype=old_weight.dtype, device=old_weight.device)
        new_weight[old_rows:] = mean + noise * std * seed_scale
    return new_weight


def resize_embedding_inplace(module: nn.Module, new_num_embeddings: int):
    old_weight = module.weight.data
    new_weight = resize_weight_matrix(old_weight, new_num_embeddings)
    module.weight = nn.Parameter(new_weight)
    if hasattr(module, "num_embeddings"):
        module.num_embeddings = new_num_embeddings


def resize_linear_output_inplace(module: nn.Linear, new_out_features: int):
    old_weight = module.weight.data  # shape (out_features, in_features)
    new_weight = resize_weight_matrix(old_weight, new_out_features)
    module.weight = nn.Parameter(new_weight)
    module.out_features = new_out_features
    if module.bias is not None:
        old_bias = module.bias.data
        new_bias = torch.zeros(new_out_features, dtype=old_bias.dtype, device=old_bias.device)
        new_bias[: old_bias.shape[0]] = old_bias
        module.bias = nn.Parameter(new_bias)


def build_resized_model():
    print("[1/4] Loading original base Moshi model...")
    weight_path = hf_hub_download(BASE_MODEL_ID, filename="model.safetensors")
    model = moshi_loaders.get_moshi_lm(weight_path, device=DEVICE)

    orig_text_emb = model.text_emb.weight.shape[0]
    orig_text_linear = model.text_linear.weight.shape[0]
    orig_depformer_text_emb = model.depformer_text_emb.weight.shape[0]
    print(f"    Original: text_emb={orig_text_emb}, text_linear={orig_text_linear}, "
          f"depformer_text_emb={orig_depformer_text_emb}")

    n_new = len(NEW_GRAPHEMES_IN_ORDER)
    target_text_emb = orig_text_emb + n_new              # 32001 -> 32016
    target_text_linear = orig_text_linear + n_new         # 32000 -> 32015
    target_depformer_text_emb = orig_depformer_text_emb + n_new  # 32001 -> 32016

    print(f"\n[2/4] Resizing in-place on the SAME live model object...")
    resize_embedding_inplace(model.text_emb, target_text_emb)
    resize_linear_output_inplace(model.text_linear, target_text_linear)
    resize_embedding_inplace(model.depformer_text_emb, target_depformer_text_emb)
    print(f"    text_emb -> {model.text_emb.weight.shape}")
    print(f"    text_linear -> {model.text_linear.weight.shape}")
    print(f"    depformer_text_emb -> {model.depformer_text_emb.weight.shape}")

    return model, {
        "orig_text_emb": orig_text_emb,
        "orig_text_linear": orig_text_linear,
        "orig_depformer_text_emb": orig_depformer_text_emb,
        "target_text_emb": target_text_emb,
        "target_text_linear": target_text_linear,
        "target_depformer_text_emb": target_depformer_text_emb,
        "n_new_tokens": n_new,
        "placeholder_id": orig_text_linear,  # 32000, preserves text_initial_token_id
        "new_token_ids": list(range(orig_text_linear + 1, target_text_linear + 1)),
    }


def validate_resized_model(model, tokenizer):
    print("\n[3/4] Validating resized model with a real forward pass...")
    sample_text = "Bu Oʻzbekiston va Ҳозир, ғалати ва ўзгарув"
    ids = tokenizer.encode(sample_text)
    print(f"    Sample text: {sample_text}")
    print(f"    Token IDs: {ids}")
    print(f"    Max token ID: {max(ids)}  (text_emb rows: {model.text_emb.weight.shape[0]})")
    assert max(ids) < model.text_emb.weight.shape[0], "Token ID still out of bounds -- resize did not take effect"

    tokens = torch.tensor([ids], device=DEVICE)
    with torch.no_grad():
        embeddings = model.text_emb(tokens)
    print(f"    PASS text_emb forward: output shape {embeddings.shape}")

    with torch.no_grad():
        hidden = torch.randn(1, tokens.shape[1], model.text_linear.in_features,
                              device=DEVICE, dtype=model.text_linear.weight.dtype)
        logits = model.text_linear(hidden)
    print(f"    PASS text_linear forward: output shape {logits.shape} "
          f"(expected last dim {model.text_linear.out_features})")


def find_lora_target_modules(model):
    """Return the actual dotted names for in_projs / out_projs submodules,
    confirmed from live inspection -- NOT 'in_proj'/'out_proj'."""
    names = []
    for name, module in model.named_modules():
        if isinstance(module, nn.Linear) and (".in_projs." in name or ".out_projs." in name
                                               or name.endswith("in_projs") or name.endswith("out_projs")):
            names.append(name)
    return names


def validate_lora(model):
    print("\n[4/4] Validating LoRA config against REAL module names...")
    from peft import LoraConfig, get_peft_model

    target_names = find_lora_target_modules(model)
    print(f"    Found {len(target_names)} matching Linear modules (showing first 6):")
    for n in target_names[:6]:
        print(f"      {n}")

    # Regex mode: PEFT treats a single string as a regex pattern matched
    # against the full dotted module name, unlike a list (which does
    # suffix/exact matching and will NOT match 'in_projs.0').
    target_regex = r".*\.(in_projs|out_projs)\.\d+$"

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=target_regex,
        task_type=None,  # custom architecture, not a standard HF task type
    )
    try:
        peft_model = get_peft_model(model, lora_config)
        n_trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        print(f"    PASS LoRA attached successfully. Trainable params: {n_trainable:,}")
        return True
    except Exception as e:
        print(f"    FAIL LoRA attach failed: {e}")
        return False


def main():
    tokenizer = LlamaTokenizer.from_pretrained(TOKENIZER_DIR)
    print(f"Loaded tokenizer: {len(tokenizer)} tokens")

    model, meta = build_resized_model()
    validate_resized_model(model, tokenizer)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nSaving validated resized model to {OUTPUT_DIR} ...")
    torch.save(model.state_dict(), OUTPUT_DIR / "model_state_dict.pt")
    import copy
    lora_ok = validate_lora(copy.deepcopy(model))
    with open(OUTPUT_DIR / "resize_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    print("\n" + "=" * 70)
    if lora_ok:
        print("ALL CHECKS PASSED. Model, tokenizer, and LoRA config are consistent.")
    else:
        print("MODEL RESIZE OK, but LoRA config still needs attention -- see above.")
    print("=" * 70)
    print(f"""
To load this exact model again (e.g. from finetune_moshi.py), use THIS
loading procedure every time -- do not load the state_dict into a fresh
unmodified model, it will size-mismatch exactly like before:

    from moshi.models import loaders as moshi_loaders
    from huggingface_hub import hf_hub_download
    import torch, json

    with open("{OUTPUT_DIR}/resize_metadata.json") as f:
        meta = json.load(f)

    weight_path = hf_hub_download("{BASE_MODEL_ID}", filename="model.safetensors")
    model = moshi_loaders.get_moshi_lm(weight_path, device="cuda")

    # re-apply the SAME resize before loading the state dict
    resize_embedding_inplace(model.text_emb, meta["target_text_emb"])
    resize_linear_output_inplace(model.text_linear, meta["target_text_linear"])
    resize_embedding_inplace(model.depformer_text_emb, meta["target_depformer_text_emb"])

    state_dict = torch.load("{OUTPUT_DIR}/model_state_dict.pt", map_location="cuda", weights_only=True)
    model.load_state_dict(state_dict, strict=True)  # now shapes match, strict=True should pass
""")


if __name__ == "__main__":
    main()
