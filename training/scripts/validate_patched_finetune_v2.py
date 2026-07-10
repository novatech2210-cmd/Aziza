#!/usr/bin/env python3
"""
validate_patched_finetune_v2.py

Validates the patched finetune setup. Loads model via state_dict to avoid FSDP issues.
"""

import os
import sys
import torch

TOKENIZER_PATH = "/root/aziza-build/model_cache/moshi-extended-vocab-fixed"
MODEL_STATE_DICT = "/root/aziza-build/model_cache/moshi-extended-model/model_state_dict.pt"
ORIGINAL_CHECKPOINT = "/root/aziza-build/model_cache/models--kyutai--moshika-pytorch-bf16/snapshots/a49141e28b3d9c947cf9aa5314431e1b11cbd2f5/model.safetensors"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

UZBEK_GRAPHEMES = [
    "Oʻ", "oʻ", "Gʻ", "gʻ", "ʻ",
    "Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў",
]

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

errors = []
warnings = []
model = None
tokenizer = None

print("="*60)
print("VALIDATING PATCHED FINETUNE SETUP")
print("="*60)

# ============================================================================
# TEST 1: Load tokenizer
# ============================================================================
print("\n[TEST 1] Loading fixed tokenizer...")
try:
    from transformers import LlamaTokenizer
    tokenizer = LlamaTokenizer.from_pretrained(TOKENIZER_PATH)
    vocab_size = len(tokenizer)
    print(f"    Tokenizer loaded: {vocab_size} tokens")

    placeholder_id = tokenizer.convert_tokens_to_ids("<reserved_text_initial_32000>")
    if placeholder_id == 32000:
        print(f"    {PASS} Placeholder at ID 32000")
    else:
        print(f"    {FAIL} Placeholder at ID {placeholder_id}, expected 32000")
        errors.append("Placeholder ID mismatch")

    all_correct = True
    for i, g in enumerate(UZBEK_GRAPHEMES):
        expected_id = 32001 + i
        toks = tokenizer.tokenize(g)
        actual_id = tokenizer.convert_tokens_to_ids(toks[0])
        if actual_id != expected_id:
            print(f"    {FAIL} '{g}' -> ID {actual_id}, expected {expected_id}")
            errors.append(f"Uzbek token '{g}' ID mismatch")
            all_correct = False

    if all_correct:
        print(f"    {PASS} All Uzbek graphemes at correct IDs (32001-32015)")

except Exception as e:
    print(f"    {FAIL} Error loading tokenizer: {e}")
    errors.append(f"Tokenizer load failed: {e}")

# ============================================================================
# TEST 2: Load extended model via state_dict
# ============================================================================
print("\n[TEST 2] Loading extended model via state_dict...")
try:
    from moshi.models import loaders, lm
    from safetensors.torch import load_file

    # Load base model from original checkpoint
    print("    Loading base model architecture...")
    model = loaders.get_moshi_lm(ORIGINAL_CHECKPOINT, device=DEVICE)
    model = model.to(torch.bfloat16)
    print(f"    Base model loaded on {DEVICE}")

    # Load resized state_dict
    print("    Loading resized state_dict...")
    state_dict = torch.load(MODEL_STATE_DICT, map_location=DEVICE)
    missing, unexpected = model.load_state_dict(state_dict, strict=False)

    if missing:
        print(f"    {WARN} Missing keys: {missing[:3]}{'...' if len(missing)>3 else ''}")
        warnings.append(f"Missing keys: {missing}")
    if unexpected:
        print(f"    {WARN} Unexpected keys: {unexpected[:3]}{'...' if len(unexpected)>3 else ''}")
        warnings.append(f"Unexpected keys: {unexpected}")

    model.eval()
    print(f"    Model ready")

    text_emb_shape = model.text_emb.weight.shape
    text_linear_shape = model.text_linear.weight.shape

    print(f"    text_emb:     {text_emb_shape}")
    print(f"    text_linear:  {text_linear_shape}")

    if text_emb_shape[0] == 32016:
        print(f"    {PASS} text_emb has 32016 rows")
    else:
        print(f"    {FAIL} text_emb has {text_emb_shape[0]} rows, expected 32016")
        errors.append("text_emb size mismatch")

    if text_linear_shape[0] == 32015:
        print(f"    {PASS} text_linear has 32015 outputs")
    else:
        print(f"    {FAIL} text_linear has {text_linear_shape[0]} outputs, expected 32015")
        errors.append("text_linear size mismatch")

    if hasattr(model, 'depformer_text_emb') and model.depformer_text_emb is not None:
        dep_shape = model.depformer_text_emb.weight.shape
        print(f"    depformer_text_emb: {dep_shape}")
        if dep_shape[0] == 32016:
            print(f"    {PASS} depformer_text_emb has 32016 rows")
        else:
            print(f"    {FAIL} depformer_text_emb has {dep_shape[0]} rows, expected 32016")
            errors.append("depformer_text_emb size mismatch")

except Exception as e:
    print(f"    {FAIL} Error loading model: {e}")
    errors.append(f"Model load failed: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 3: Verify embedding accessors
# ============================================================================
print("\n[TEST 3] Checking embedding accessors...")
if model is not None:
    try:
        input_emb = model.text_emb
        output_emb = model.text_linear

        print(f"    text_emb type: {type(input_emb).__name__}")
        print(f"    text_linear type: {type(output_emb).__name__}")

        if hasattr(model, 'emb') and model.emb is not model.text_emb:
            print(f"    {PASS} moshi_lm.emb is separate from text_emb")
        else:
            print(f"    {WARN} Could not verify emb separation")

    except Exception as e:
        print(f"    {FAIL} Error checking embeddings: {e}")
        errors.append(f"Embedding check failed: {e}")
else:
    print(f"    {FAIL} Model not loaded, skipping")
    errors.append("Model not loaded for embedding check")

# ============================================================================
# TEST 4: Verify LoRA target modules
# ============================================================================
print("\n[TEST 4] Checking LoRA target modules...")
if model is not None:
    try:
        target_modules = ["in_proj", "out_proj", "linear1", "linear2"]
        found_modules = []

        for name, module in model.named_modules():
            for target in target_modules:
                if target in name and isinstance(module, torch.nn.Linear):
                    found_modules.append(name)

        print(f"    Found {len(found_modules)} Linear modules matching targets")
        for m in found_modules[:8]:
            print(f"      {m}")
        if len(found_modules) > 8:
            print(f"      ... and {len(found_modules) - 8} more")

        if len(found_modules) > 0:
            print(f"    {PASS} Found LoRA-compatible target modules")
        else:
            print(f"    {FAIL} No LoRA-compatible modules found")
            errors.append("No LoRA target modules found")

    except Exception as e:
        print(f"    {FAIL} Error checking modules: {e}")
        errors.append(f"Module check failed: {e}")
else:
    print(f"    {FAIL} Model not loaded, skipping")
    errors.append("Model not loaded for module check")

# ============================================================================
# TEST 5: Forward pass with Uzbek text
# ============================================================================
print("\n[TEST 5] Running forward pass with Uzbek text...")
if model is not None and tokenizer is not None:
    try:
        test_text = "Salom, Oʻzbekiston! Ўзбекистон ҳақида гапирайлик."

        tokens = tokenizer.encode(test_text, return_tensors="pt").to(DEVICE)
        print(f"    Input tokens: {tokens.shape}")
        print(f"    Token IDs: {tokens[0].tolist()[:20]}...")

        max_tid = tokens.max().item()
        print(f"    Max token ID: {max_tid}")

        if max_tid >= model.text_emb.weight.shape[0]:
            print(f"    {FAIL} Max token ID {max_tid} >= text_emb rows {model.text_emb.weight.shape[0]}")
            errors.append(f"Token ID {max_tid} out of embedding bounds")
        else:
            print(f"    {PASS} All token IDs within embedding bounds")

        with torch.no_grad():
            embeddings = model.text_emb(tokens)
        print(f"    Embeddings shape: {embeddings.shape}")
        print(f"    {PASS} Embedding lookup successful")

        with torch.no_grad():
            flat = embeddings.view(-1, embeddings.shape[-1])
            logits = model.text_linear(flat)
        print(f"    Logits shape: {logits.shape}")

        if logits.shape[-1] == 32015:
            print(f"    {PASS} Output logits dimension matches (32015)")
        else:
            print(f"    {FAIL} Output logits dim {logits.shape[-1]}, expected 32015")
            errors.append("Output logits dimension mismatch")

    except Exception as e:
        print(f"    {FAIL} Forward pass error: {e}")
        errors.append(f"Forward pass failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"    {FAIL} Model or tokenizer not loaded, skipping")
    errors.append("Model/tokenizer not loaded for forward pass")

# ============================================================================
# TEST 6: PEFT/LoRA compatibility
# ============================================================================
print("\n[TEST 6] Checking PEFT/LoRA compatibility...")
if model is not None:
    try:
        from peft import LoraConfig, get_peft_model

        lora_config = LoraConfig(
            r=8,
            lora_alpha=16,
            target_modules=["in_proj", "out_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )

        peft_model = get_peft_model(model, lora_config)
        print(f"    {PASS} PEFT LoRA wrapper applied successfully")

        trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in peft_model.parameters())
        print(f"    Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.4f}%)")

        if trainable > 0 and trainable < total:
            print(f"    {PASS} LoRA correctly freezes base model")
        else:
            print(f"    {WARN} Unexpected trainable parameter count")

    except ImportError:
        print(f"    {WARN} PEFT not installed, skipping LoRA test")
        warnings.append("PEFT not installed")
    except Exception as e:
        print(f"    {FAIL} LoRA wrapping failed: {e}")
        errors.append(f"LoRA test failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"    {FAIL} Model not loaded, skipping")
    errors.append("Model not loaded for LoRA test")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "="*60)
print("VALIDATION SUMMARY")
print("="*60)

if not errors and not warnings:
    print("\n" + "\033[92m" + "ALL TESTS PASSED — READY FOR TRAINING" + "\033[0m")
    print("\nYou can now run finetune_moshi.py with confidence.")
    sys.exit(0)
elif not errors:
    print(f"\n{WARN}: {len(warnings)} warning(s), 0 errors")
    for w in warnings:
        print(f"  - {w}")
    print("\nSetup should work, but review warnings above.")
    sys.exit(0)
else:
    print(f"\n{FAIL}: {len(errors)} error(s), {len(warnings)} warning(s)")
    for e in errors:
        print(f"  - {e}")
    for w in warnings:
        print(f"  - {w}")
    print("\nFix errors before starting training.")
    sys.exit(1)

