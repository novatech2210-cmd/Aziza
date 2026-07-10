from huggingface_hub import hf_hub_download
from moshi.models import loaders
p = hf_hub_download("kyutai/moshika-pytorch-bf16", "model.safetensors")
m = loaders.get_moshi_lm(p, device="cpu")
print("zero_token_id  :", m.zero_token_id)
print("delays         :", m.delays)
print("audio_offset   :", m.audio_offset)
print("num_codebooks  :", m.num_codebooks)
print("dep_q          :", m.dep_q)
# Check initial token
tok = m._get_initial_token()
print("initial token  :", tok.shape, tok.min().item(), tok.max().item())
