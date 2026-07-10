import os
from huggingface_hub import login, hf_hub_download

token = os.environ.get('HF_TOKEN') or os.environ.get('HUGGINGFACE_TOKEN')
if not token:
    raise RuntimeError("HF_TOKEN or HUGGINGFACE_TOKEN environment variable not set")
login(token=token)

print("Downloading Moshi model...")
try:
    hf_hub_download(repo_id='kyutai/moshika-pytorch-bf16', filename='model.safetensors', cache_dir='/root/aziza-build/model_cache')
    print("Done downloading model.safetensors!")
except Exception as e:
    print("Error:", e)
