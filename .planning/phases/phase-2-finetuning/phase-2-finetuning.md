# Phase 2 — Fine-Tuning Pipeline (Voice-to-Voice)
> Derived from AI-SPEC-Aziza.md. Scope: produce and validate LoRA adapters for PersonaPlex/Moshi
> (Russian registers + Uzbek Latin/Cyrillic). This phase applies to the **voice-to-voice mode only**.
> Prerequisite: Phase 1 complete (stable orchestrator, working audio pipeline, sufficient disk headroom).

---

## Goal
Train, merge, and load language/persona adapters for PersonaPlex so voice-to-voice sessions can switch
between Russian professional/colloquial/academic registers and Uzbek Latin/Cyrillic without corrupting
audio output or breaking session state.

---

## Critical Failure Modes In Scope

1. **`dep_q` mismatch** — training with `dep_q=8` instead of `dep_q=16` → corrupted audio output from
   fine-tuned adapters. `dep_q=16` is a hard requirement enforced by `loaders._load_hook`, but custom
   loading code can bypass it silently — verify explicitly after every adapter load.
2. **Disk pressure** — fine-tuning artifacts and checkpoints can exhaust the ~30GB free headroom flagged
   at the last audit. Confirm space before each training run, not just at phase start.
3. **Adapter bleed** — wrong LoRA adapter loaded for a session's language → wrong phoneme/lexical
   distribution in output.

---

## Tasks

| Task | Command / File | Status |
|---|---|---|
| Confirm GPU capacity on `aziza-worker-01` (or provision dedicated GPU host via Proxmox) | Proxmox panel `83.126.40.53:8006` | |
| Re-check disk headroom before starting | `aziza-worker-01` | |
| Generate dialogue data for Russian (3 registers × 10k pairs) | `pipeline/generate_dialogues_sync.py` | |
| Generate dialogue data for Uzbek Latin + Cyrillic | `pipeline/generate_dialogues_sync.py` | |
| Train adapters: `dep_q=16, rank=128, skip_depformer=true` | `moshi-finetune/train.py` | |
| Merge LoRA → `model.safetensors` | `pipeline/merge_lora.py` | |
| Load adapter into moshi-worker | `moshi_engine.load_adapter()` | |
| Eval perplexity per adapter | eval script | |
| Time adapter hot-swap (<30s target) | `moshi_engine.load_adapter()` timing test | |

---

## Implementation Notes

### Installation
```bash
cd moshi-finetune && pip install -e .
pip install flash-attn --no-build-isolation  # match CUDA version
```

### Training Config (non-negotiable)
- `dep_q=16` — **never** `dep_q=8`. This is enforced by `loaders._load_hook` on load, but is not
  enforced at train time by custom scripts — double-check the training config explicitly.
- `rank=128`
- `skip_depformer=true`

### Adapters In Scope
| Adapter | Language | Register |
|---|---|---|
| `ru_professional` | Russian | Professional/business |
| `ru_colloquial` | Russian | Casual/conversational (already in use for ASR — keep phoneme distribution consistent) |
| `ru_academic` | Russian | Formal/academic |
| `uz_latin` | Uzbek | Latin script |
| `uz_cyrillic` | Uzbek | Cyrillic script |

### Prompt Wrapping (shared convention with text-to-text)
System prompts are tokenized via `sentencepiece` at session start and stored as
`lm_gen.text_prompt_tokens`. They are loss-masked during training (`system_prompt: true` in config).
Use the same `<system>...<system>` wrapping convention used in text-to-text/voice-to-text for
consistency across modes.

```python
def wrap_system_prompt(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("<system>") and cleaned.endswith("<system>"):
        return cleaned
    return f"<system> {cleaned} <system>"
```

---

## Evaluation Strategy

| Dimension | Rubric | Measurement Approach | Priority |
|---|---|---|---|
| **Language accuracy** | Russian response when `adapter=ru_*`; Uzbek when `adapter=uz_*` | LLM Judge: Claude grades transcript language | High |
| **Register consistency** | Professional register in professional adapter; colloquial in colloquial | LLM Judge: rubric-based tone scoring | High |
| **Phoneme quality** | MOS (Mean Opinion Score) >3.5 for Russian output | Human: native speaker rating panel | High |
| **Adapter load time** | LoRA adapter hot-swap completes in <30s | Code: timing test in `moshi_engine.load_adapter()` | Medium |
| **Audio integrity post-adapter-load** | No corruption introduced by adapter switch | Code: `mean_abs` + screech detector check after each load | Critical |

### Eval Tooling
```bash
pip install arize-phoenix opentelemetry-sdk opentelemetry-exporter-otlp
python -m phoenix.server.main serve --port 6006
```
```python
from opentelemetry import trace
tracer = trace.get_tracer("aziza.moshi-worker")
```

### Reference Dataset (this phase's slice)
- 5x Russian colloquial: casual conversation, slang tolerance
- 5x Uzbek Latin: basic queries + persona check
- 5x Edge cases: mid-call adapter swap
- 5x Failure regression: previously failing inputs (screech triggers, silence loops)

Labeling: native speaker panel (2 reviewers per sample, average) for audio quality; automated
`langdetect` + human spot-check for language accuracy; Claude as LLM judge for persona/register fidelity.

---

## Verification Plan

### Automated Tests
```bash
pytest tests/test_dep_q_enforcement.py -v       # confirm dep_q=16 on every adapter load
pytest tests/test_adapter_load_timing.py -v      # <30s hot-swap
python scripts/eval_adapter_perplexity.py --adapter ru_professional
python scripts/eval_adapter_perplexity.py --adapter ru_colloquial
python scripts/eval_adapter_perplexity.py --adapter ru_academic
python scripts/eval_adapter_perplexity.py --adapter uz_latin
python scripts/eval_adapter_perplexity.py --adapter uz_cyrillic
```

### Manual Verification
- Native Russian speaker panel rates MOS on a sample of professional/colloquial/academic outputs.
- Native Uzbek speaker validates Latin and Cyrillic adapter outputs.
- Mid-call adapter swap test: start a session in `ru_professional`, swap to `ru_colloquial`
  mid-conversation, confirm no audio corruption and persona/register actually shifts.

---

## Exit Criteria
- [ ] All 5 adapters trained with `dep_q=16` confirmed (not silently defaulted to 8)
- [ ] Each adapter merges cleanly to `model.safetensors`
- [ ] Adapter hot-swap completes in <30s
- [ ] MOS >3.5 for Russian adapters (native speaker panel)
- [ ] Uzbek Latin/Cyrillic outputs validated by native speaker
- [ ] No audio corruption introduced by adapter switching (verified via `mean_abs` + screech detector)
- [ ] Disk headroom maintained throughout (re-checked, not just at phase start)
