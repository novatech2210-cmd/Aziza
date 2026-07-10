from transformers import AutoModelForCausalLM
import sys

print("Loading Moshi model on CPU to inspect layers...")
try:
    model = AutoModelForCausalLM.from_pretrained(
        "kyutai/moshiko-pytorch-bf16",
        device_map="cpu",
        trust_remote_code=True,
    )
    for name, module in model.named_modules():
        if "audio" in name.lower() or "emb" in name.lower() or "linear" in name.lower() or "norm" in name.lower():
            print(name)
except Exception as e:
    print("Error:", e)
