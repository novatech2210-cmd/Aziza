import os
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
if not os.environ.get("HF_TOKEN"):
    raise RuntimeError("HF_TOKEN environment variable not set")

from huggingface_hub import snapshot_download

print("Downloading Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24...")
path = snapshot_download(repo_id="Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24")
print(f"Downloaded to {path}")
