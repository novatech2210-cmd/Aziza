# Uzbek Adapter Analysis

## Summary

The Uzbek LoRA adapter (`aziza_uzbek`) **cannot be loaded** into the deployed Moshi model due to a fundamental architecture mismatch. This is a pre-existing condition documented in `CURRENT_TASK.md` and confirmed by runtime logs.

## Root Cause

| Component | Expected by Adapter | Actual in Moshi |
|-----------|---------------------|-----------------|
| Base model | `Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24` (Llama-based) | `kyutai/moshika-pytorch-bf16` (Moshi architecture) |
| Target modules | `q_proj`, `k_proj`, `v_proj`, `o_proj` (standard Llama attention layers) | Moshi uses different internal layer names; these modules do not exist |
| Adapter config | `base_model_name_or_path: Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24` | N/A — different model entirely |

### Evidence

Runtime error from `moshi_engine.py`:
```
Failed to load PEFT adapters: Target modules {'q_proj', 'o_proj', 'v_proj', 'k_proj'} not found in the base model.
```

Adapter config (`/root/aziza-build/training/lora/adapters/aziza-adapter-final-uz/adapter_config.json`):
```json
{
  "base_model_name_or_path": "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24",
  "target_modules": ["v_proj", "q_proj", "o_proj", "k_proj"]
}
```

Moshi model architecture (`kyutai/moshika-pytorch-bf16`) does not expose `q_proj`, `k_proj`, `v_proj`, or `o_proj` as named modules. The Moshi LM uses a custom streaming transformer architecture with different parameter naming.

## Impact

- **Voice-to-voice**: Moshi runs in base mode (no LoRA adapters). Audio encoding/decoding works. Text generation is routed to external vLLM services (English: port 8002, Uzbek: port 8003).
- **Uzbek LLM inference**: Works correctly via vLLM (`/root/aziza-build/model_cache/alloma-extended-model/`) with extended tokenizer (vocab 128,272).
- **Russian LLM inference**: Works correctly via vLLM (`Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24`) with `ru_all` LoRA adapter.

## Why This Cannot Be Fixed by Reconfiguration

1. **Architecture mismatch is structural**: PEFT/LoRA adapters are tightly coupled to the base model's module hierarchy. You cannot load a Llama-trained adapter into a Moshi model without retraining.
2. **No Moshi-compatible LoRA exists**: There is no known LoRA adapter trained specifically on the `kyutai/moshika-pytorch-bf16` architecture for Uzbek.
3. **Tokenizer mismatch compounds the issue**: Even if the architecture matched, the adapter was trained with a different tokenizer vocabulary.

## Remediation Options

### Option A: Retrain Moshi LoRA for Uzbek (Recommended for Production)

Train a new LoRA adapter specifically on the Moshi architecture for Uzbek language:

- **Base model**: `kyutai/moshika-pytorch-bf16`
- **Training data**: Uzbek speech + text pairs
- **Expected duration**: 4-8 hours on A6000
- **Output**: Adapter compatible with Moshi's module structure
- **Risk**: Requires maintenance window and training expertise

### Option B: Accept Base Moshi + External vLLM (Current Architecture)

Continue using the existing pipeline:
- Moshi handles audio encoding/decoding (base model)
- Uzbek text generation handled by Alloma vLLM (port 8003)
- This is the current production configuration

**Trade-off**: Moshi's audio processing is not fine-tuned for Uzbek phonetics, but the external LLM handles language generation correctly.

### Option C: Architecture Substitution (Not Recommended)

Replace Moshi with a Llama-based model that matches the adapter's expected architecture. This violates the Architecture Freeze and would require extensive re-engineering of the audio pipeline.

## Decision

**Adopt Option B for now. Document Option A as a future training task.**

The adapter mismatch is a pre-existing technical debt item. It does not block the LiveKit integration or multilingual voice certification, because:
- Uzbek LLM inference works via vLLM
- Moshi audio processing works in base mode
- The external LLM handles language-specific generation

## Action Items

1. ✅ **Documented**: This analysis file committed to `engineering/UZBEK_ADAPTER_ANALYSIS.md`
2. **Future**: Create GSD task for Moshi LoRA retraining (requires 4-8hr maintenance window)
3. **No code changes required**: Current production configuration is stable
