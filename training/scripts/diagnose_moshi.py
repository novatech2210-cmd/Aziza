import torch
import json
from huggingface_hub import hf_hub_download
from moshi.models import loaders

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Loading base Moshi LM...")
try:
    moshi_path = hf_hub_download("kyutai/moshika-pytorch-bf16", "model.safetensors", local_files_only=True)
    moshi_lm = loaders.get_moshi_lm(moshi_path, device=device)
    print("Moshi LM loaded successfully.")
except Exception as e:
    print(f"Error loading Moshi LM: {e}")
    import sys
    sys.exit(1)

config_path = "/root/aziza-build/aziza-multilingual-adapter/final/adapter_config.json"
try:
    with open(config_path, "r") as f:
        adapter_config = json.load(f)
    print("\n--- Adapter Config ---")
    print("Target modules:", adapter_config.get("target_modules", []))
except Exception as e:
    print(f"Error reading adapter config: {e}")

print("\n--- Base Model Sample Modules (q_proj, k_proj, v_proj, o_proj) ---")
for name, module in list(moshi_lm.named_modules())[:300]:
    if any(x in name for x in ["q_proj", "k_proj", "v_proj", "o_proj", "proj"]):
        print(name)

