import torch
import json
from huggingface_hub import hf_hub_download
from moshi.models import loaders

device = "cuda" if torch.cuda.is_available() else "cpu"
moshi_path = hf_hub_download("kyutai/moshika-pytorch-bf16", "model.safetensors", local_files_only=True)
moshi_lm = loaders.get_moshi_lm(moshi_path, device=device)

print("\n--- Base Model Sample Modules (linear_in, linear_out) ---")
found_in = False
found_out = False
for name, module in moshi_lm.named_modules():
    if "linear_in" in name:
        print(name)
        found_in = True
    if "linear_out" in name:
        print(name)
        found_out = True

if not found_in: print("linear_in NOT FOUND")
if not found_out: print("linear_out NOT FOUND")

