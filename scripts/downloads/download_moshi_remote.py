import os
from huggingface_hub import login, hf_hub_download

token = os.environ.get('HF_TOKEN') or os.environ.get('HUGGINGFACE_TOKEN')
if not token:
    raise RuntimeError("HF_TOKEN or HUGGINGFACE_TOKEN environment variable not set")
login(token=token)

print("Downloading Moshi models...")
files = [
    'model.safetensors',
    'tokenizer-e351c8d8-checkpoint125.safetensors',
    'tokenizer_spm_32k_3.model'
]

for filename in files:
    try:
        hf_hub_download(repo_id='kyutai/moshiko-pytorch-bf16', filename=filename)
        print(f"Done downloading {filename}!")
    except Exception as e:
        print(f"Error downloading {filename}:", e)
