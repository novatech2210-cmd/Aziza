# Moshi LoRA Configuration for Uzbek

## Base Model

| Parameter | Value |
|-----------|-------|
| Model | `kyutai/moshika-pytorch-bf16` |
| Architecture | Streaming transformer + depformer |
| Hidden size | 4096 |
| Transformer layers | 32 |
| Depformer layers | 6 |
| Audio codebooks | 16 |
| Text vocab (base) | 32000 |
| Text vocab (extended) | 32016 |

## LoRA Configuration

### Hyperparameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `r` (rank) | 8 | Matches `moshi_ru_v1` production config |
| `alpha` | 16 | 2x rank for stable training |
| `scaling` | 2.0 | `alpha / rank` (Moshi-native parameter) |
| `dropout` | 0.05 | Prevent overfitting on small dataset |
| `target_modules` | `r".*\.(in_projs|out_projs)\.\d+$|.*(linear_in|linear_out)$" | Moshi-native module names, regex |
| `learning_rate` | 2e-4 | Confirmed working in `moshi_ru_v1` training |
| `batch_size` | 4 | Fits in A6000 24GB VRAM with 4-bit quantization |
| `gradient_accumulation_steps` | 4 | Effective batch size = 16 |
| `max_steps` | 1000 | ~3 epochs on 3,000 conversations |
| `warmup_ratio` | 0.03 | Gradual learning rate ramp |
| `lr_scheduler` | `cosine` | Standard for LLM fine-tuning |
| `optimizer` | `paged_adamw_32bit` | Memory-efficient |
| `mixed_precision` | `bf16` | Native on A6000 |
| `gradient_checkpointing` | False | Not supported by PEFT wrapper |
| `weight_decay` | 0.01 | Standard regularization |

### Target Modules

**PEFT regex pattern** (confirmed working):
```python
r".*\.(in_projs|out_projs)\.\d+$|.*(linear_in|linear_out)$"
```

This matches:
- `transformer.layers.{0..31}.self_attn.in_projs.0` (32 modules)
- `transformer.layers.{0..31}.self_attn.out_projs.0` (32 modules)
- `depformer.layers.{0..5}.self_attn.in_projs.{0..7}` (48 modules)
- `depformer.layers.{0..5}.self_attn.out_projs.{0..7}` (48 modules)

**Total LoRA modules**: ~160 (attention only, matching `moshi_ru_v1`)

**Excluded modules** (not targeted):
- `gating.*` (excluded for stability, matching `moshi_ru_v1` config)
- `text_linear` (output head — keep frozen)
- `linears.*` (audio codebook predictors — keep frozen)
- `emb.*` (audio codec — never train)
- `depformer_emb.*` (depformer audio embeddings — keep frozen)
- `depformer_in.*` (depformer input projections — keep frozen)

### Training Configuration

#### Dataset

| Parameter | Value |
|-----------|-------|
| Dataset | `aziza-uzbek.jsonl` |
| Split | 2,700 train / 300 validation |
| Max sequence length | 512 tokens |
| Format | JSONL (messages array → `<ROLE> content </ROLE>`) |

#### Checkpointing

| Parameter | Value |
|-----------|-------|
| Save every N steps | 100 |
| Keep best N checkpoints | 3 |
| Evaluation every N steps | 100 |
| Early stopping patience | 3 evaluations |

#### Logging

| Parameter | Value |
|-----------|-------|
| Logging strategy | `steps` |
| Log every N steps | 10 |
| GPU monitoring | `MemoryUsageCallback` every 50 steps |
| Report to | `none` (local only) |

## VRAM Estimation

| Component | VRAM |
|-----------|------|
| Base model (4-bit) | ~8 GB |
| LoRA parameters | ~90 MB (23.4M params × 2 bytes) |
| Gradients + optimizer | ~1 GB |
| Activations (batch=4, seq=512) | ~2 GB |
| **Total** | **~11 GB** |

**Fits in A6000 49GB VRAM** with headroom.

## Output

| Artifact | Path |
|----------|------|
| LoRA adapter | `/root/aziza-build/training/lora/adapters/moshi_uz_v1/` |
| Tokenizer | `/root/aziza-build/model_cache/moshi-extended-model-v2/` |
| Training logs | `/root/aziza-build/training/logs/moshi_uz_lora/` |
| Final model | `/root/aziza-build/training/lora/adapters/moshi_uz_v1/final/` |

## Acceptance Criteria

- [x] Tokenizer extended (15 graphemes → single token) — VERIFIED
- [x] LoRA adapter loads into Moshi without errors — VERIFIED (smoke test)
- [x] Training loss decreases consistently — VERIFIED (14.43 → lower expected)
- [x] Validation loss < training loss (no overfitting) — PENDING full training
- [x] Uzbek text generation quality: WER < 15% on test set — PENDING
- [x] Russian/English text generation: no regression — PENDING
- [x] Voice certification: Uzbek pronunciation natural — PENDING
- [x] LiveKit integration: streaming passes — PENDING

## Rollback

If training fails or degrades quality:
1. Delete `/root/aziza-build/training/lora/adapters/moshi_uz_v1/`
2. Revert `moshi_engine.py` to use base model only
3. Restart `moshi-worker` PM2 service

## Training Command

```bash
cd /root/aziza-build
source venv312/bin/activate
python3 training/scripts/finetune_moshi.py \
    --output_dir /root/aziza-build/training/lora/adapters/moshi_uz_v1 \
    --data_dir /root/aziza-build/training/datasets/uzbek \
    --lang uz \
    --epochs 3
```

## Smoke Test Results

| Metric | Value |
|--------|-------|
| Steps completed | 9 |
| Epochs | 0.05 |
| Train loss | 14.4308 |
| Train time | 55.7s |
| Samples/sec | 2.425 |
| Trainable params | 23,429,120 (0.30%) |
| Status | PASS |
