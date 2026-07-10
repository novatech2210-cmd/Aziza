import os
from huggingface_hub import snapshot_download, login

token = os.environ.get('HF_TOKEN') or os.environ.get('HUGGINGFACE_TOKEN')
if not token:
    raise RuntimeError("HF_TOKEN or HUGGINGFACE_TOKEN environment variable not set")
login(token=token)

cache_dir = '/root/aziza-build/model_cache'
os.makedirs(cache_dir, exist_ok=True)

print("Downloading moshika-pytorch-bf16...")
try:
    snapshot_download(repo_id='kyutai/moshika-pytorch-bf16', local_dir=os.path.join(cache_dir, 'moshika-pytorch-bf16'))
    print("Success for moshika!")
except Exception as e:
    print(f"Error: {e}")

print("Downloading mimi...")
try:
    snapshot_download(repo_id='kyutai/mimi', local_dir=os.path.join(cache_dir, 'mimi'))
    print("Success for mimi!")
except Exception as e:
    print(f"Error: {e}")
