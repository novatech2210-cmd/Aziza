from modelscope.hub.snapshot_download import snapshot_download

print("Downloading Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24 from ModelScope...")
model_dir = snapshot_download('Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24', cache_dir='/home/kali/.cache/huggingface/hub')
print(f"Downloaded to {model_dir}")
