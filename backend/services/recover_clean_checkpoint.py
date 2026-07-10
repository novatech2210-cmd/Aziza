import json
import torch
from pathlib import Path
from huggingface_hub import hf_hub_download
from moshi.models import loaders as moshi_loaders
from peft import LoraConfig, get_peft_model

from resize_and_validate_moshi import (
    resize_embedding_inplace,
    resize_linear_output_inplace,
    BASE_MODEL_ID,
    OUTPUT_DIR,
    DEVICE,
)

CONTAMINATED_PATH = OUTPUT_DIR / "model_state_dict.pt"
CLEAN_PATH = OUTPUT_DIR / "model_state_dict_clean.pt"

with open(OUTPUT_DIR / "resize_metadata.json") as f:
    meta = json.load(f)

print("[1/5] Loading original base Moshi model...")
weight_path = hf_hub_download(BASE_MODEL_ID, filename="model.safetensors")
model = moshi_loaders.get_moshi_lm(weight_path, device=DEVICE)

print("[2/5] Re-applying the exact same resize...")
resize_embedding_inplace(model.text_emb, meta["target_text_emb"])
resize_linear_output_inplace(model.text_linear, meta["target_text_linear"])
resize_embedding_inplace(model.depformer_text_emb, meta["target_depformer_text_emb"])

print("[3/5] Wrapping with the SAME LoRA config used during the contaminated save...")
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=r".*\.(in_projs|out_projs)\.\d+$",
    task_type=None,
)
peft_model = get_peft_model(model, lora_config)

print("[4/5] Loading the contaminated state dict into the matching wrapped structure...")
state = torch.load(CONTAMINATED_PATH, map_location=DEVICE, weights_only=True)
# NOTE: get_peft_model() mutated `model`'s submodules in place, so the
# contaminated checkpoint's keys match `model`'s own state_dict() paths
# directly (no "base_model.model." prefix) -- load into `model`, not peft_model.
missing, unexpected = model.load_state_dict(state, strict=False)
print(f"    missing: {len(missing)} keys, unexpected: {len(unexpected)} keys")
if unexpected:
    print("    First few unexpected:", unexpected[:5])
assert len(unexpected) == 0, "Wrapper still doesn't match — do not proceed to unload()"

print("[5/5] Unwrapping LoRA and saving clean state dict...")
clean_model = peft_model.unload()
torch.save(clean_model.state_dict(), CLEAN_PATH)
print(f"Saved clean checkpoint to {CLEAN_PATH}")
