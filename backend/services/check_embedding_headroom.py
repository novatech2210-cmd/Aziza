"""
check_embedding_headroom.py

Moshi CANNOT be loaded via AutoModelForCausalLM (confirmed -- this is why
extend_tokenizer_vocab.py's step 5 failed). It must go through
moshi.models.loaders.get_moshi_lm(), same as finetune_moshi.py does.

The wrapper class in finetune_moshi.py hardcodes vocab_size=32768 as a
default, while the SentencePiece tokenizer only defines 32000 pieces.
32768 = 2^15, which suggests the checkpoint may have been built with
padding headroom. This script checks the ACTUAL embedding matrix shape
to find out whether our 15 new token IDs (32000-32014) already have
real rows waiting, or whether a true resize is still needed.
"""

from huggingface_hub import hf_hub_download
from moshi.models import loaders as moshi_loaders

BASE_MODEL_ID = "kyutai/moshika-pytorch-bf16"

print(f"Downloading weights for {BASE_MODEL_ID} ...")
weight_path = hf_hub_download(BASE_MODEL_ID, filename="model.safetensors")

print("Loading native Moshi LM ...")
moshi_lm = moshi_loaders.get_moshi_lm(weight_path, device="cpu")

emb = moshi_lm.emb
print(f"\nEmbedding module type: {type(emb)}")
print(f"Embedding module: {emb}")

# Try to get the actual shape depending on module type
if hasattr(emb, "weight"):
    print(f"\nEmbedding weight shape: {emb.weight.shape}")
    actual_rows = emb.weight.shape[0]
elif hasattr(emb, "num_embeddings"):
    actual_rows = emb.num_embeddings
    print(f"\nnum_embeddings: {actual_rows}")
else:
    print(f"\nUnrecognized embedding structure, attrs: {dir(emb)}")
    actual_rows = None

TOKENIZER_VOCAB_SIZE = 32000
NEW_TOKENS_NEEDED = 15
NEEDED_ROWS = TOKENIZER_VOCAB_SIZE + NEW_TOKENS_NEEDED  # 32015

if actual_rows is not None:
    print(f"\n--- Result ---")
    print(f"Tokenizer defines:      {TOKENIZER_VOCAB_SIZE} pieces")
    print(f"New tokens added:       {NEW_TOKENS_NEEDED} (IDs 32000-32014)")
    print(f"Rows needed:            {NEEDED_ROWS}")
    print(f"Actual embedding rows:  {actual_rows}")
    if actual_rows >= NEEDED_ROWS:
        print(f"\n>>> HEADROOM EXISTS. No resize needed.")
        print(f">>> IDs 32000-32014 already have embedding rows (untrained,")
        print(f">>> near-init values). LoRA/fine-tuning will train them")
        print(f">>> naturally along with everything else.")
    else:
        print(f"\n>>> NO HEADROOM. True resize required before training.")
        print(f">>> Need {NEEDED_ROWS - actual_rows} more rows than exist.")
