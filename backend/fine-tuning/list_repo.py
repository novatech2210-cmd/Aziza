from huggingface_hub import list_repo_files
import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
try:
    files = list_repo_files("kyutai/moshika-pytorch-bf16")
    for f in files:
        print(f)
except Exception as e:
    print(e)
