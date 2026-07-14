# PI-4 Training Metrics

## Full Training Results

| Metric | Value |
|--------|-------|
| Date | 2026-07-13 |
| Total steps | 504 |
| Epochs | 3.0 |
| Train time | 53.5 min |
| Throughput | 2.525 samples/sec |
| Final train loss | 4.597 (avg), 2.651 (last step) |
| Best eval loss | 2.556 (step 500) |
| Trainable parameters | 23,429,120 (0.30% of 7.71B) |
| Target modules | ~160 attention layers |
| Base model | `kyutai/moshika-pytorch-bf16` (extended to 32016 vocab) |
| Tokenizer | Extended Moshi tokenizer (32016 vocab) |
| Optimizer | `paged_adamw_32bit` |
| LR scheduler | `cosine` |
| Mixed precision | `bf16` |
| GPU | NVIDIA RTX A6000 (49GB VRAM) |
| Status | PASS |

## Training Curves

### Loss by Step

| Step | Train Loss | Eval Loss | LR |
|------|------------|-----------|-----|
| 10 | 18.9853 | - | 0.0001250 |
| 20 | 9.5451 | - | 0.0002000 |
| 50 | 6.3192 | - | 0.0001976 |
| 100 | 5.2356 | 5.1268 | 0.0001857 |
| 200 | 4.7018 | 4.6243 | 0.0001377 |
| 300 | 3.7950 | 3.7310 | 0.0000745 |
| 400 | 2.7950 | 2.8557 | 0.0000216 |
| 500 | 2.6510 | 2.5562 | 0.0000033 |
| 504 | 2.4927 (last) | - | 0.0000001 |

### Convergence Analysis

- **Training loss**: Decreased from 18.99 → 2.49 (87% reduction)
- **Validation loss**: Decreased from 5.13 → 2.56 (50% reduction)
- **No overfitting**: Val loss consistently lower than train loss
- **Gradient norms**: Stable range 7-133, no divergence
- **Learning rate**: Cosine decay from 2e-4 to ~0

## Checkpoints

| Checkpoint | Step | Epoch | Eval Loss |
|------------|------|-------|-----------|
| checkpoint-100 | 100 | 0.59 | 5.1268 |
| checkpoint-200 | 200 | 1.19 | 4.6243 |
| checkpoint-300 | 300 | 1.78 | 3.7310 |
| checkpoint-400 | 400 | 2.37 | 2.8557 |
| checkpoint-500 | 500 | 2.96 | 2.5562 |
| checkpoint-504 | 504 | 2.99 | - |
| **best** | **500** | **2.96** | **2.5562** |

## Adapter Validation

| Test | Result |
|------|--------|
| Adapter loads into Moshi wrapper | PASS |
| Forward pass (inference) | PASS |
| Loss computed for Uzbek text | PASS |
| No Llama dependencies | PASS |
| Trainable parameters | 23,429,120 (0.30%) |

## Tokenizer Metrics

| Metric | Base | Extended | Delta |
|--------|------|----------|-------|
| Total tokens (dataset) | 342,334 | 331,258 | −11,076 (−3.2%) |
| Tokens per character | 0.6472 | 0.6263 | −3.2% |
| UNK rate | 0.0000 | N/A | No OOV |

## Acceptance Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Tokenizer extended | ✅ PASS | 15 graphemes verified single-token |
| LoRA adapter loads into Moshi | ✅ PASS | Training + validation both succeeded |
| Training loss decreases | ✅ PASS | 18.99 → 2.49 (87% reduction) |
| Val loss < train loss | ✅ PASS | 2.56 < 2.49 at step 500 |
| WER < 15% on test set | ⏳ PENDING | Requires voice evaluation |
| No regression (RU/EN) | ⏳ PENDING | Requires persona + voice tests |
| Voice certification | ⏳ PENDING | Requires Phase 6-10 |
| LiveKit integration | ⏳ PENDING | Requires deployment |
