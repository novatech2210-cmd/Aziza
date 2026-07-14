# Moshi Architecture Analysis

## Model Information

- **Repository**: `kyutai/moshika-pytorch-bf16`
- **Snapshot**: `a49141e28b3d9c947cf9aa5314431e1b11cbd2f5`
- **Model type**: `LMModel`
- **Architecture**: Streaming transformer with dependencyformer (depformer)

## Core Specifications

| Parameter | Value | Source |
|-----------|-------|--------|
| Total parameters | 7,711,300,608 | `sum(p.numel() for p in model.parameters())` |
| Hidden size | 4096 | `transformer.layers.0.self_attn.in_projs.0.weight.shape = [12288, 4096]` |
| Transformer layers | 32 | `transformer.layers.0` through `transformer.layers.31` |
| Attention heads | 32 | `12288 / 4096 / 3 = 32` (QKV fused) |
| Head dimension | 128 | `4096 / 32 = 128` |
| Depformer layers | 6 | `depformer.layers.0` through `depformer.layers.5` |
| Depformer hidden | 1024 | `depformer.layers.0.self_attn.in_projs.0.weight.shape = [3072, 1024]` |
| Audio codebooks | 16 | `emb.0` through `emb.15` (16 audio streams) |
| Text codebooks | 1 | `text_emb` (1 text stream) |
| Total codebooks | 17 | `model.num_codebooks = 17` |
| Delays | `[0,0,1,1,1,1,1,1,1,0,1,1,1,1,1,1,1]` | `model.delays` |
| Text vocab (base) | 32000 | `tokenizer_spm_32k_3.model` |
| Text vocab (extended) | 32016 | base 32000 + reserved 32000 + 15 Uzbek graphemes |
| Audio vocab | 2049 | `emb.0.weight.shape = [2049, 4096]` |
| Audio silence token | 2048 | `model.ungenerated_token_id = -2`, `zero_token_id = -1`, audio_card=2048 |
| BOS token | 1 | `<s>` |
| EOS token | 2 | `</s>` |
| PAD token | 3 | `<pad>` |
| UNK token | 0 | `<unk>` |

## Module Structure

### Transformer (Main Language Model)
- `transformer.layers.X.self_attn.in_projs.0`: Linear([12288, 4096]) — fused QKV projection
- `transformer.layers.X.self_attn.out_projs.0`: Linear([4096, 4096]) — output projection
- `transformer.layers.X.gating.linear_in`: Linear([22528, 4096]) — audio gating input
- `transformer.layers.X.gating.linear_out`: Linear([4096, 11264]) — audio gating output

### Depformer (Dependency Transformer for Audio)
- `depformer.layers.X.self_attn.in_projs.Y`: Linear([3072, 1024]) × 8 codebooks per layer
- `depformer.layers.X.self_attn.out_projs.Y`: Linear([1024, 1024]) × 8 codebooks per layer
- `depformer.layers.X.gating.Y.linear_in`: Linear([5632, 1024]) × 8 codebooks per layer
- `depformer.layers.X.gating.Y.linear_out`: Linear([1024, 2816]) × 8 codebooks per layer

### Output Heads
- `text_emb`: ScaledEmbedding([32016, 4096]) — text token embeddings
- `text_linear`: Linear([32016, 4096]) — text vocabulary projection
- `linears.X`: Linear([2048, 1024]) × 8 — audio codebook predictors
- `emb.X`: ScaledEmbedding([2049, 4096]) × 16 — audio codebook embeddings
- `depformer_emb.X`: ScaledEmbedding([2049, 1024]) × 8 — depformer audio embeddings
- `depformer_text_emb`: ScaledEmbedding([32016, 1024]) — depformer text embedding
- `depformer_in.X`: Linear([1024, 4096]) × 8 — depformer input projections

## Adapter Injection Points

For LoRA fine-tuning, target modules must use Moshi-native names:

```
transformer.layers.{0..31}.self_attn.in_projs.0
transformer.layers.{0..31}.self_attn.out_projs.0
transformer.layers.{0..31}.gating.linear_in
transformer.layers.{0..31}.gating.linear_out
depformer.layers.{0..5}.self_attn.in_projs.{0..7}
depformer.layers.{0..5}.self_attn.out_projs.{0..7}
depformer.layers.{0..5}.gating.{0..7}.linear_in
depformer.layers.{0..5}.gating.{0..7}.linear_out
```

**PEFT regex pattern** (confirmed working):
```python
r".*\.(in_projs|out_projs)\.\d+$|.*(linear_in|linear_out)$"
```

**Total LoRA modules**: ~512 (32×4 transformer + 6×8×8 depformer)

## Codec Information

- **Codec**: Mimi (from `kyutai/moshika-pytorch-bf16`)
- **Sample rate**: 24kHz
- **Channels**: 1 (mono)
- **Frame rate**: 12.5 Hz (80ms frames)
- **Audio card**: 2049 (2048 silence + 1 active)

## Comparison with Failed Adapter

| Aspect | Failed Adapter | Moshi Native |
|--------|---------------|--------------|
| Base model | `Vikhrmodels/Vikhr-Llama3.1-8B` | `kyutai/moshika-pytorch-bf16` |
| Target modules | `q_proj`, `k_proj`, `v_proj`, `o_proj` | `in_projs.0`, `out_projs.0`, `gating.*` |
| Architecture | Llama-decoder | Streaming transformer + depformer |
| Vocab | 32000+ (Qwen2) | 32016 (SentencePiece + extended) |
| Compatible | ❌ No | ✅ Yes |

## Decision

**Do NOT attempt to load the existing `aziza_uzbek` adapter.** It is trained on a completely different architecture.

**Proceed with:**
1. Extend Moshi tokenizer for Uzbek (15 graphemes) — COMPLETED
2. Train new LoRA adapter on native Moshi architecture — PIPELINE VERIFIED
3. Validate with voice certification tests — PENDING
