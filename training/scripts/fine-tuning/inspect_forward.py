from moshi.models import loaders
import inspect
from huggingface_hub import hf_hub_download
p = hf_hub_download("kyutai/moshika-pytorch-bf16", "model.safetensors")
m = loaders.get_moshi_lm(p, device="cpu")
print("forward signature:", inspect.signature(m.forward))
