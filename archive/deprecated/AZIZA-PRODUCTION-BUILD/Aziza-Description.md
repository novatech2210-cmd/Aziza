# Aziza AI Platform - Master Production Build

## 1. Complete Stack Overview

### 1.1 Architecture Decision Record
* **Base Model**: Vikhr-Llama-3.1-8B-Instruct (4-bit NF4 Quantization)
* **Voice Inference**: Moshi Full-Duplex Engine
* **Gateway**: NestJS
* **Telephony**: Asterisk ARI + FFmpeg + Python asyncio
* **Orchestrator**: Redis Pub/Sub for dynamic worker routing
* **Frontend**: Vue 3 + Pinia (Text chat & Voice UI AudioWorklets)
* **Database**: PostgreSQL
* **Infrastructure**: Vast.ai H100 Instance managed by PM2 and systemd. No Docker.

### 1.2 Three Interaction Modes
1. **Text → Text**: Standard web chat utilizing vLLM and a custom QLoRA adapter for sub-3-second responses.
2. **Voice → Text**: Browser mic (WebAudio API) → 16kHz PCM → WebSocket → Moshi ASR → transcript → LLM → text response.
3. **Voice ↔ Voice (Full Duplex)**: Simultaneous bidirectional audio. PCM frames are streamed over WebSockets (via browser AudioWorklet) or RTP/SIP trunks (via Asterisk ARI + FFmpeg), allowing zero-VAD-latency conversational flow and natural interruptions.

### 1.3 Language Routing
Every session carries a language tag: `ru | uz-latin | uz-cyrillic`. The NestJS Gateway uses this tag to:
1. Select the correct QLoRA adapter
2. Inject the correct PersonaPlex system prompt
3. Apply the language drift guard (retry if >10% ASCII in response for non-English)

## 2. Current Status - What Is Done vs Pending

* Russian QLoRA adapter eval passed (≥80% Cyrillic accuracy): ✅ Done
* TTFT p95 <100ms - Russian: ✅ Done
* Text→Text: Russian coherent response in <3s: ✅ Done
* PersonaPlex: Aziza stays in character 5+ turns (Russian): ✅ Done
* *Other tests for Uzbek and Voice/TTFT are pending execution.*

## 3. Phase 2 - Uzbek Language Completion
Uzbek datasets are available on HuggingFace and must be used immediately without waiting for custom datasets.

**Datasets Used:**
* Uzbek Latin — Primary (52K instruction pairs): `behbudiy/alpaca-cleaned-uz`
* Uzbek Latin — Secondary (52K, independent translation): `saillab/alpaca-uzbek-cleaned`
* Uzbek Bilingual — Professional register (20K): `behbudiy/translation-instruction`
* Uzbek Cyrillic — Book corpus (40K books): `tahrirchi/uz-books`

## 4. Environment & Configuration Reference

### 4.1 Required Environment Variables
* `HF_TOKEN`: All training + serving scripts
* `MODEL_ID`: `Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24`
* `ADAPTER_PATH_RU`: `/root/aziza/adapters/ru_colloquial`
* `ADAPTER_PATH_UZ_LATIN`: `/root/aziza/adapters/uz_colloquial`
* `ADAPTER_PATH_UZ_CYRILLIC`: `/root/aziza/adapters/uz_cyrillic`
* `REDIS_URL`: `redis://localhost:6379`
* `JWT_SECRET`: Random hex string for Gateway Auth
* `DATABASE_URL`: `postgresql://aziza:pw@localhost/aziza_db`
* `WORKER_ID`: Used by each Moshi worker process
* `WS_PORT`: Worker instance port (e.g. 8021, 8022...)
* `ASTERISK_URL`, `ASTERISK_USER`, `ASTERISK_PASS`: ARI telephony integration

### 4.2 Locked Training Config (Do Not Change)
```python
LOCKED_CONFIG = {
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "max_seq_length": 512,
    "batch_size": 4,
    "grad_accum_steps": 4,
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "lr_scheduler_type": "cosine",
    "quantization": "nf4",
    "double_quant": True,
    "compute_dtype": "float16",
}
```

## 5. Final Production Acceptance Checklist
* [x] Russian QLoRA adapter eval passed (≥80% Cyrillic accuracy)
* [x] TTFT p95 <100ms — Russian
* [x] Text→Text: Russian coherent response in <3s
* [x] PersonaPlex: Aziza stays in character 5+ turns (Russian)
* [ ] Uzbek Latin QLoRA adapter eval passed (≥80% accuracy)
* [ ] Uzbek Cyrillic QLoRA adapter eval passed (≥80% accuracy)
* [ ] TTFT p95 <100ms — Uzbek Latin
* [ ] TTFT p95 <100ms — Uzbek Cyrillic
* [ ] Text→Text: Uzbek Latin coherent response in <3s
* [ ] Text→Text: Uzbek Cyrillic coherent response in <3s
* [ ] Voice→Text: transcript <2s after end-of-speech (Russian)
* [ ] Voice→Text: transcript <2s after end-of-speech (Uzbek)
* [ ] Voice↔Voice browser: audio round-trip <300ms (Russian)
* [ ] Voice↔Voice browser: audio round-trip <300ms (Uzbek)
* [ ] Voice↔Voice phone (SIP): end-to-end call working (Russian)
* [ ] Voice↔Voice phone (SIP): end-to-end call working (Uzbek)
* [ ] PersonaPlex: Aziza stays in character 5+ turns (Uzbek)
* [ ] 10-minute continuous session — no crash, no memory leak
* [ ] PM2 ecosystem starts all services from cold boot
* [ ] Git repo created, all assets committed, branch protection on
* [ ] All adapter .tar.gz backups stored off-GPU (RU Done / UZ Pending)
