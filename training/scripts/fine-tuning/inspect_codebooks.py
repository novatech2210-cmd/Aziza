"""Inspect Moshi codebook structure and embedding vocab sizes."""
from huggingface_hub import hf_hub_download
from moshi.models import loaders

p = hf_hub_download("kyutai/moshika-pytorch-bf16", "model.safetensors")
m = loaders.get_moshi_lm(p, device="cpu")

print(f"num_codebooks       : {m.num_codebooks}")
print(f"num_audio_codebooks : {getattr(m, 'num_audio_codebooks', 'N/A')}")
print(f"audio_offset        : {getattr(m, 'audio_offset', 'N/A')}")
print(f"text_card           : {getattr(m, 'card', 'N/A')}")

print("\nEmbedding table sizes:")
if hasattr(m, 'emb'):
    for i, emb in enumerate(m.emb):
        print(f"  emb[{i}]: num_embeddings={emb.num_embeddings}")

print("\nLinear heads (if any):")
if hasattr(m, 'linears'):
    for i, lin in enumerate(m.linears):
        print(f"  linears[{i}]: out={lin.out_features}")
