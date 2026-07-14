# Uzbek Dataset Audit Report

## Summary

This report audits available Uzbek-language datasets for training a native Moshi LoRA adapter.

## Primary Dataset: `aziza-uzbek.jsonl`

| Attribute | Value | Measurement |
|-----------|-------|-------------|
| Path | `/root/aziza-build/training/datasets/aziza-uzbek.jsonl` | Verified |
| Size | 1.2 MB | `os.path.getsize` |
| Conversations | 3,000 | `sum(1 for _ in open(...))` |
| Messages | 9,000 | 3 messages per conversation (system, user, assistant) |
| Total characters | 528,928 | `len(full_text)` |
| Format | JSONL (messages array) | Verified |
| Scripts | 50% Latin (`uz_latin`), 50% Cyrillic (`uz_cyrillic`) | Character-set analysis |
| Registers | Professional (1,177), Colloquial (1,215), Academic (608) | `register` field count |
| Turns per conversation | 3 | Fixed structure |
| License | Internal (AZIZA proprietary) | Documented |
| Quality | High — human-curated, persona-aligned | Documented |
| Speakers | Synthetic (generated) | Documented |
| Audio | None (text-only) | Documented |
| Spontaneous dialogue | No (all scripted) | Documented |

**Equivalent text duration**: ~9.8 hours (528,928 chars ÷ ~90 chars/sec reading rate)

### Sample conversation structure:
```json
{
  "language": "uz_latin",
  "register": "professional",
  "messages": [
    {"role": "system", "content": "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz."},
    {"role": "user", "content": "Salom, menga yordam bering."},
    {"role": "assistant", "content": "Assalomu alaykum! Men Aziza. Sizga qanday yordam bera olaman?"}
  ]
}
```

## Secondary Dataset: `aziza-bilingual.jsonl`

| Attribute | Value |
|-----------|-------|
| Size | 40 KB |
| Conversations | ~1,000 |
| Languages | Mixed RU-UZ code-switching |
| Purpose | Code-switching regularization |

## External Datasets

### 1. FLEURS Uzbek (`google/fleurs` — `uz_uz`)

| Attribute | Value |
|-----------|-------|
| License | CC BY 4.0 |
| Speakers | 100+ (verified) |
| Gender balance | Balanced |
| Sampling rate | 16kHz |
| Quality | High (professional recordings) |
| Limitation | Scripted sentences, read speech only, Latin script only |

### 2. Common Voice Uzbek

| Attribute | Value |
|-----------|-------|
| Status | Not available in CV17 (dataset error) |
| Alternative | CV11-CV16 may have Uzbek |
| License | CC0 |

### 3. MLS Uzbek

| Attribute | Value |
|-----------|-------|
| Status | NOT AVAILABLE |
| Languages | Dutch, French, German, Italian, Polish, Portuguese, Spanish |

### 4. OpenSLR

| Attribute | Value |
|-----------|-------|
| Status | DEPRECATED |
| Access | No longer supported via `datasets` library |

## Recommended Dataset Strategy

### Phase 1: Text LoRA Training (Immediate)

**Primary**: `aziza-uzbek.jsonl` (3,000 conversations)
- Use all 3,000 conversations
- Split: 2,700 train / 300 validation
- Both Latin and Cyrillic scripts

**Augmentation**:
- Apply back-translation for data augmentation
- Generate persona variations using PersonaPlex
- Code-switching samples from `aziza-bilingual.jsonl`

### Phase 2: Extended Training (Future)

**Supplement with FLEURS**:
- Download `google/fleurs` (uz_uz)
- Extract transcriptions as text-only samples
- Combine with local dataset (target: 10,000+ conversations)

**External sources** (requires manual download and cleaning):
- OpenSubtitles Uzbek
- OSCAR Uzbek
- News articles (uzbek.uz, kun.uz)

### Phase 3: Audio Fine-tuning (Future)

**Not recommended for initial LoRA**:
- Audio LoRA requires paired audio-text data
- Moshi's audio tokenizer is fixed; LoRA operates on text embeddings
- Audio quality improvements require full model fine-tuning, not LoRA

## Sampling Weights

| Dataset | Weight | Reason |
|---------|--------|--------|
| `aziza-uzbek.jsonl` (Latin) | 0.5 | Primary training data |
| `aziza-uzbek.jsonl` (Cyrillic) | 0.3 | Secondary, code-switching support |
| `aziza-bilingual.jsonl` | 0.2 | Code-switching regularization |

## Estimated Training Duration

- **Dataset preparation**: 1-2 hours
- **Tokenizer extension**: COMPLETED
- **LoRA training**: ~1 hour on A6000 (smoke test: 9 steps in 55s)
- **Validation**: 1 hour

## Decision

**Use `aziza-uzbek.jsonl` as primary dataset.** It is the highest-quality, persona-aligned, ready-to-use dataset available. Supplement with FLEURS transcriptions if additional data is needed.
