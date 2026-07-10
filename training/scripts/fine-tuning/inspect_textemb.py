from huggingface_hub import hf_hub_download
from moshi.models import loaders

p = hf_hub_download("kyutai/moshika-pytorch-bf16", "model.safetensors")
m = loaders.get_moshi_lm(p, device="cpu")

print("text_emb vocab size:", m.text_emb.num_embeddings)
print("text_card (text_linear out):", m.text_linear.out_features if hasattr(m, 'text_linear') else "N/A")

# What tokenizer does Moshi use?
try:
    from sentencepiece import SentencePieceProcessor
    import os
    tok_path = hf_hub_download("kyutai/moshika-pytorch-bf16", "tokenizer_spm_32k_3.model")
    spm = SentencePieceProcessor(model_file=tok_path)
    print("SPM vocab size:", spm.vocab_size())
    test = spm.encode("Hello world")
    print("Test encode 'Hello world':", test, "max id:", max(test))
except Exception as e:
    print("SPM load failed:", e)
