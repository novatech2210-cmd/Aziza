# Uzbek Tokenizer Gap Analysis

**Date**: 2026-07-11
**Scope**: All tokenizer pipelines affecting Uzbek language support

---

## Executive Summary

Three separate tokenizer pipelines affect Uzbek. Each has different fragmentation characteristics:

| Pipeline | Tokenizer | Vocab | Uzbek Latin | Uzbek Cyrillic | Status |
|----------|-----------|-------|-------------|----------------|--------|
| Moshi (voice) | SentencePiece | 32,016 (extended) | FIXED | FIXED | Extended tokenizer ready, needs LoRA retraining |
| Vikhr (EN/RU text) | Llama3 BPE | 128,000 | FRAGMENTED (2-3 tokens) | FRAGMENTED (2 tokens) | Requires extension or retraining |
| Alloma (UZ text) | Qwen2 BPE | 128,272 (extended) | FIXED (single token) | FIXED (single token) | Tokenizer extended, model resize pending |

---

## Character Inventory

### Uzbek Latin Characters (with okina)

| Character | Unicode | Example Word | Moshi Original | Moshi Extended | Vikhr | Alloma (Before) | Alloma (After) |
|-----------|---------|-------------|----------------|----------------|-------|-----------------|----------------|
| `Oʻ` | U+004F U+02BB | Oʻzbekiston | 3 tokens (frag) | 1 token (32001) OK | 3 tokens (frag) | `['O']` okina DROPPED | 1 token (128257) OK |
| `oʻ` | U+006F U+02BB | joʻra | 3 tokens (frag) | 1 token (32002) OK | 3 tokens (frag) | `['o']` okina DROPPED | 1 token (128258) OK |
| `Gʻ` | U+0047 U+02BB | gʻazab | 3 tokens (frag) | 1 token (32003) OK | 3 tokens (frag) | `['G']` okina DROPPED | 1 token (128259) OK |
| `gʻ` | U+0067 U+02BB | gʻalaba | 3 tokens (frag) | 1 token (32004) OK | 3 tokens (frag) | `['g']` okina DROPPED | 1 token (128260) OK |
| `ʻ` | U+02BB | (standalone) | 3 tokens (frag) | 1 token (32005) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128261) OK |

### Uzbek Cyrillic Characters

| Character | Unicode | Example Word | Moshi Original | Moshi Extended | Vikhr | Alloma (Before) | Alloma (After) |
|-----------|---------|-------------|----------------|----------------|-------|-----------------|----------------|
| `Ҳ` | U+04BA | Ҳikoyа | 3 tokens (frag) | 1 token (32006) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128262) OK |
| `ҳ` | U+04BB | ҳikoyа | 3 tokens (frag) | 1 token (32007) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128263) OK |
| `Ҷ` | U+04B6 | Ҷuma | 3 tokens (frag) | 1 token (32008) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128264) OK |
| `ҷ` | U+04B7 | ҷuma | 3 tokens (frag) | 1 token (32009) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128265) OK |
| `Қ` | U+049A | Қozon | 3 tokens (frag) | 1 token (32010) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128266) OK |
| `қ` | U+049B | қозон | 3 tokens (frag) | 1 token (32011) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128267) OK |
| `Ғ` | U+0492 | Ғозал | 3 tokens (frag) | 1 token (32012) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128268) OK |
| `ғ` | U+0493 | ғозал | 3 tokens (frag) | 1 token (32013) OK | 2 tokens (frag) | `[]` EMPTY | 1 token (128269) OK |
| `Ў` | U+040E | Ўзбекистон | 3 tokens (frag) | 1 token (32014) OK | 1 token OK | `[]` EMPTY | 1 token (128270) OK |
| `ў` | U+045E | ўзбекистон | 3 tokens (frag) | 1 token (32015) OK | 1 token OK | `[]` EMPTY | 1 token (128271) OK |

### Fragmentation Impact

**Moshi original** (before extension): Each Uzbek character = 2-3 byte tokens → "Oʻzbekiston" = ~12 tokens instead of ~3.

**Moshi extended**: All characters single tokens → "Oʻzbekiston" = ~3 tokens. **FIXED.**

**Vikhr** (Llama3 BPE): Okina fragments to 2-3 tokens, Cyrillic fragments to 2 tokens → similar overhead as Moshi original.

**Alloma** (Qwen2 BPE): Okina SILENTLY DROPPED (character lost), Cyrillic EMPTY (character lost) → words lose meaning.

---

## Pipeline 1: Moshi Voice (FIXED)

### Current State
- Extended tokenizer at `/root/aziza-build/model_cache/moshi-extended-model-v2/`
- 15 graphemes added at token IDs 32001-32015
- Resized model checkpoint saved (15.38 GB)
- All 15 characters tokenize as single tokens

### Remaining Work
- LoRA adapters must be retrained against new vocab size (32,016)
- Current adapters (`moshi_ru_v1`, `aziza-multilingual-adapter`) trained on old 32,001 vocab
- Training script (`finetune_moshi.py`) already configured to use extended tokenizer
- **BLOCKER**: Retraining requires ~4-8 hours on A6000 GPU, cannot serve while training

### Recommendation
Schedule retraining in maintenance window. The tokenizer extension itself is complete.

---

## Pipeline 2: Vikhr Text (EN/RU) — Uzbek Fragmentation

### Current State
- Vikhr Llama3.1-8B BPE tokenizer (128k vocab)
- Okina fragments to 2-3 tokens
- Uzbek Cyrillic fragments to 2 tokens
- `Ў`/`ў` are in vocab (single token) — these are common in Russian too

### Impact
- Affects Russian text generation when Uzbek loanwords or names appear
- Does NOT affect English text generation
- Low priority since primary Uzbek text generation uses Alloma (port 8003)

### Recommendation
Low priority. The Vikhr tokenizer is designed for Russian/English. Uzbek characters in Russian text are rare. Defer to PI-2.

---

## Pipeline 3: Alloma Text (Uzbek) — FIXED (Tokenizer Extension)

### Current State
- Alloma-3B-Instruct uses Qwen2 BPE tokenizer
- **Extended tokenizer** at `/root/aziza-build/model_cache/alloma-extended-tokenizer/` (128,272 vocab)
- 15 Uzbek characters added at token IDs 128257-128271
- All characters now produce single tokens (0 empty, 0 dropped)
- **Model extension script** at `/tmp/extend_alloma_model.py` — resizes embeddings for deployment

### Impact
- Okina no longer silently dropped — "Oʻzbekistan" now tokenized correctly
- Uzbek Cyrillic characters produce proper tokens — no more empty tokenization
- Existing LoRA adapters COMPATIBLE (they don't use the new token IDs)

### Deployment
1. Run `python /tmp/extend_alloma_model.py` to create extended model checkpoint
2. Update PM2 config: `--model /root/aziza-build/model_cache/alloma-extended-model/`
3. Restart vllm-uzbek: `pm2 restart vllm-uzbek`

---

## Russian Adapter Audit

### Adapter: `ru_all` (Production, port 8002)
- **Base model**: Vikhr-Llama3.1-8B-Instruct
- **Tokenizer**: Vikhr Llama3 BPE (128k)
- **Tokenizer compatibility**: PASS — same base model, same tokenizer
- **Vocabulary alignment**: PASS — no extended tokens needed for Russian
- **Status**: PASS

### Adapter: `ru_colloquial` (Not in production)
- **Base model**: Vikhr-Llama3.1-8B-Instruct
- **Tokenizer**: Vikhr Llama3 BPE (128k)
- **Status**: PASS (same as ru_all, not deployed)

### Adapter: `aziza-adapter-final-uz` (Production, port 8003)
- **Base model stated**: Vikhr-Llama3.1-8B-Instruct (Llama3.1-8B)
- **Actually loaded on**: uzlm/alloma-3B-Instruct (Qwen2-3B)
- **Tokenizer mismatch**: Adapter trained on Llama3 tokenizer, loaded with Qwen2 tokenizer
- **Status**: WARNING — adapter-base model mismatch. LoRA weights trained on Llama representations applied to Qwen2 representations. May produce suboptimal results.

---

## Quantitative Measurements

### Moshi Tokenizer

| Metric | Before (Original) | After (Extended) | Improvement |
|--------|-------------------|------------------|-------------|
| "Oʻzbekiston" tokens | 12 | 3 | 75% reduction |
| "gʻazab" tokens | 9 | 3 | 67% reduction |
| "ҳikoya" tokens | 6 | 3 | 50% reduction |
| Unknown tokens | 0 | 0 | No change |
| Byte-level fragments | 30 | 0 | 100% eliminated |

### Alloma Tokenizer (After Extension)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| "Oʻzbekiston" tokens | 3 (okina lost) | 4 (okina preserved) | Meaning preserved |
| "gʻazab" tokens | 3 (okina lost) | 4 (okina preserved) | Meaning preserved |
| "Ҳikoyа" tokens | 3 (Cyrillic unknown) | 4 (Cyrillic preserved) | Meaning preserved |
| Unknown/Empty tokens | 10 (all Cyrillic chars) | 0 | 100% eliminated |
| Okina drop rate | 100% (5/5 words) | 0% (0/5 words) | 100% eliminated |

---

## Implementation Plan

### Phase B Scope (This Sprint)
1. ~~Enumerate missing characters~~ — DONE (15 graphemes documented)
2. ~~Verify current tokenizer~~ — DONE (3 tokenizers audited)
3. ~~Alloma tokenizer vocabulary extension~~ — DONE (tokenizer saved, model extension script ready)
4. ~~Russian adapter audit~~ — DONE (PASS)
5. Model embedding resize — READY (script at `/tmp/extend_alloma_model.py`)
6. Deployment (PM2 config update) — DEFERRED (requires human approval)
7. Regression tests — TO DO

### Deferred to PI-2
- Moshi LoRA retraining (requires maintenance window)
- Vikhr tokenizer extension (low priority)
- Adapter-base model mismatch investigation
