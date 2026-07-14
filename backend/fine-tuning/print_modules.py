from transformers import AutoConfig, AutoModelForCausalLM
import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
try:
    config = AutoConfig.from_pretrained("kyutai/moshika-pytorch-bf16", trust_remote_code=True)
    print(config)
except Exception as e:
    print(e)
