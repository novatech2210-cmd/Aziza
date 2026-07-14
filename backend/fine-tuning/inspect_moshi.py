from huggingface_hub import hf_hub_download
import os

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
repo_id = "kyutai/moshika-pytorch-bf16"
filename = "modeling_moshika.py"
try:
    filepath = hf_hub_download(repo_id=repo_id, filename=filename)
    print(f"Downloaded to {filepath}")
    with open(filepath, "r") as f:
        content = f.read()
        for line in content.split("\n"):
            if "nn.Linear" in line or "nn.Embedding" in line or "self." in line and "= nn." in line:
                print(line.strip())
except Exception as e:
    print(e)
