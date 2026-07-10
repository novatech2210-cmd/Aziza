import os
from transformers import AutoTokenizer
hf_token = os.environ.get("HF_TOKEN", "")
try:
    tok = AutoTokenizer.from_pretrained("nvidia/personaplex-7b-v1", token=hf_token, trust_remote_code=True)
    print("Success fast")
except Exception as e:
    print("Fast failed", e)

try:
    tok = AutoTokenizer.from_pretrained("nvidia/personaplex-7b-v1", token=hf_token, trust_remote_code=True, use_fast=False)
    print("Success slow")
except Exception as e:
    print("Slow failed", e)
