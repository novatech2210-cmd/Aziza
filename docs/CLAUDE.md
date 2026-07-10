# AZIZA PLATFORM — REVISED PHASE BUILD PLANS
**Version 2.0 — Post Phase-1 Benchmark Review**

---

## ARCHITECTURAL DECISIONS (LOCKED)

These decisions are final based on benchmark data and must be reflected in all phases:

| Decision | Detail |
|---|---|
| **Session model** | `max_sessions = 1` per GPU worker — no multi-threading |
| **Concurrency strategy** | Horizontal scaling (more workers) not vertical (more sessions per GPU) |
| **PersonaPlex role** | Dynamic prompt injection microservice — NOT trained, NOT embedded in model |
| **Personality system** | Dynamic via PersonaPlex Redis pub/sub at runtime |
| **Phonetics/language** | QLoRA LoRA r=16 adapter on Moshi text layers + audio codebooks |
| **Target latency** | <100ms TTFT per session, <500ms E2E |
| **Fine-tuning languages** | Russian, Uzbek Latin, Uzbek Cyrillic, English |
| **Training hardware** | Single H100 SXM (80GB), ~2–5 hour training run |

---

## PHASE STATUS OVERVIEW

| Phase | Title | Status |
|---|---|---|
| Phase 1 | Infrastructure Foundation | ✅ Complete |
| Phase 2 | API Gateway | ✅ Complete |
| Phase 3 | Real-Time Streaming Foundation | ✅ Complete |
| Phase 4 | Moshi Inference Runtime | 🔄 Revised — single-session focus |
| Phase 5 | Integration & Performance | 🔄 Revised — horizontal scaling validation |
| Phase 6 | PersonaPlex Integration | 🔄 Revised — dynamic injection clarified |
| Phase 7 | AI Orchestrator | 🔄 Revised — worker pool management |
| Phase 8 | Frontend Integration | ✅ Complete |
| Phase 9 | Telephony Integration | 🟡 Pending |
| Phase 10 | Monitoring & Observability | 🟡 Pending |
| Phase 11 | Multilingual Fine-Tuning | 🔴 HIGH PRIORITY — activate now |

---

## PHASE 1 — INFRASTRUCTURE FOUNDATION ✅ COMPLETE

**Goal:** Stable GPU-enabled backend infrastructure.

**Completed deliverables:**
- Docker + Docker Compose with NVIDIA Container Toolkit
- GPU visibility verified in containers
- Redis with persistent volume operational
- MongoDB with persistent volume operational
- NGINX reverse proxy with WebSocket support
- Environment configuration and centralized logging

**Architecture note (post-benchmark revision):**
GPU workers run as isolated containers, each hosting exactly one Moshi session.
The orchestrator manages a pool of these workers rather than scheduling multiple sessions
into a single container. Update `docker-compose.yml` to reflect named GPU worker replicas.

**Worker pool template (add to docker-compose.yml):**
```yaml
moshi-worker:
  image: aziza/moshi-worker
  deploy:
    replicas: N  # one per available GPU slot
  environment:
    - MAX_SESSIONS=1
    - WORKER_ID=${WORKER_ID}
  runtime: nvidia
  environment:
    NVIDIA_VISIBLE_DEVICES: ${GPU_INDEX}
```

---

## PHASE 2 — API GATEWAY ✅ COMPLETE

**Goal:** Backend communication foundation.

**Completed deliverables:**
- NestJS API Gateway with JWT + refresh tokens
- Session management and rate limiting
- WebSocket gateway (Socket.IO)
- Endpoints: `/auth`, `/session`, `/stream/start`, `/stream/stop`, `/persona`, `/health`
- Structured logging

**Revision required — worker-aware session routing:**
Session management must be updated to query the Orchestrator for an available worker
before issuing a session token. A session is only valid when bound to a specific worker ID.

**Updated session flow:**
```
Client → /session/create
  → Orchestrator.getAvailableWorker()
  → Returns { worker_id, worker_url }
  → Session token includes worker binding
  → Client WebSocket connects directly to bound worker
```

**Updated endpoints:**
- `POST /session/create` — now returns `{ session_id, worker_id, worker_ws_url }`
- `GET /session/status` — includes bound worker health
- `DELETE /session/release` — frees worker slot in orchestrator registry

---

## PHASE 3 — REAL-TIME STREAMING FOUNDATION ✅ COMPLETE

**Goal:** Real-time duplex audio streaming.

**Completed deliverables (from Phase3completion.md):**
- VAD: webrtcvad integrated, high-speed speech detection
- Interruption logic: asyncio task cancellation, <150ms response time verified
- Session state machine: IDLE → LISTENING → THINKING → SPEAKING → IDLE
- Redis pub/sub coordination with API Gateway confirmed operational

**No further work required on this phase.**
Proceed directly to Phase 4.

---

## PHASE 4 — MOSHI INFERENCE RUNTIME 🔄 REVISED

**Goal:** Deploy single-session streaming AI inference per GPU worker.

**Key revision from original plan:**
Remove ALL multi-session batching logic. This worker handles exactly ONE conversation.
KV-cache is allocated entirely to that session. No dynamic batching, no session multiplexing.

### Tasks

**Environment setup:**
- Install `moshi`, `torch`, `transformers` on worker container
- Download Moshi model weights (mimi/moshi) from Hugging Face
- Verify CUDA device assignment per worker (`CUDA_VISIBLE_DEVICES`)

**Inference engine:**
Create `moshi_engine.py`:
```python
class SingleSessionInference:
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.model = load_moshi(device=device)
        self.kv_cache = None  # Allocated fully to this one session
        self.session_active = False

    async def start_session(self, session_id: str):
        self.session_id = session_id
        self.kv_cache = self.model.init_kv_cache()
        self.session_active = True

    async def step(self, audio_chunk: bytes) -> bytes:
        # Single session — no batching, no contention
        tokens = await self.model.stream_step(audio_chunk, self.kv_cache)
        return tokens

    async def reset(self):
        # Called on interruption or session end
        self.kv_cache = self.model.init_kv_cache()
```

**Redis service wrapper:**
`moshi_service.py` — subscribe to `audio:in:{session_id}`, publish to `audio:out:{session_id}`.

**PersonaPlex context injection hook:**
Before each inference step, check Redis for pending persona context from PersonaPlex:
```python
context = await redis.get(f"persona:context:{session_id}")
if context:
    await self.model.inject_context(context)
```

**Latency targets (single session):**
- Time-to-First-Token (TTFT): <100ms
- Inter-token latency: <50ms
- Interruption response: <150ms

### Deliverables
- Functional single-session Moshi inference service per worker container
- Redis audio I/O bridge
- PersonaPlex context injection hook
- Latency benchmark: confirm TTFT <100ms for 1 session

### Validation checklist
- [ ] Single session TTFT under 100ms
- [ ] No KV-cache contention (only one session)
- [ ] Interruption resets KV-cache cleanly
- [ ] PersonaPlex context injected without blocking inference
- [ ] Worker registers healthy in Orchestrator after startup

---

## PHASE 5 — INTEGRATION & PERFORMANCE 🔄 REVISED

**Goal:** Full end-to-end pipeline validation with horizontal scaling verification.

**Key revision from original plan:**
The latency target is per-session (not aggregate across sessions).
Performance validation must include horizontal scaling: spin up 2+ workers and verify
session isolation — no cross-session audio bleed, no shared KV-cache state.

### Tasks

**PersonaPlex integration:**
- PersonaPlex service deployed as isolated FastAPI microservice
- Validates prompt assembly is <30ms overhead
- Injects persona context via Redis before each Moshi inference step

**End-to-end pipeline test:**
```
WebSocket audio → VAD → Redis queue → Moshi worker
                                    → PersonaPlex context injection
                                    → Token streaming → Audio response
                                    → WebSocket playback
```

**Performance profiling targets:**
| Metric | Target |
|---|---|
| TTFT (single session) | <100ms |
| E2E latency | <500ms |
| Interruption response | <150ms |
| PersonaPlex overhead | <30ms |
| Worker startup time | <10s |

**Horizontal scaling test:**
- Spin up 3 workers (3 sessions simultaneously)
- Verify: session A audio never appears in session B response
- Verify: each worker TTFT remains <100ms independently
- Verify: Redis channels are namespaced correctly (`audio:in:{session_id}`)

**Stability & recovery:**
- Service health checks with automatic worker restart
- Worker re-registration with Orchestrator after crash
- Redis reconnection handling in all services

### Deliverables
- Fully integrated Aziza voice pipeline
- Horizontal scaling validation report (3+ simultaneous sessions)
- Performance benchmark report confirming all targets
- Session isolation confirmation

### Validation checklist
- [ ] E2E latency under 500ms
- [ ] TTFT under 100ms per session
- [ ] 3 simultaneous sessions fully isolated
- [ ] PersonaPlex injects context in <30ms
- [ ] Worker auto-restarts and re-registers cleanly

---

## PHASE 6 — PERSONAPLEX INTEGRATION 🔄 REVISED

**Goal:** Persistent persona orchestration and dynamic context injection layer.

**Critical clarification (post-Phase-1 review):**
PersonaPlex does NOT train the model and is NOT embedded in Moshi's weights.
It is a standalone FastAPI microservice that injects personality and emotional state
as text prompts into Moshi sessions at runtime via Redis pub/sub.

**Two-layer personality architecture:**
```
Layer 1 — Phonetics (from Phase 11 fine-tuning):
  Model knows HOW to speak Russian/Uzbek naturally.
  Baked into QLoRA adapter weights.
  Cannot change at runtime.

Layer 2 — Personality (from PersonaPlex):
  Model knows WHO it is speaking as — tone, emotion, manner.
  Injected dynamically at each inference step.
  Can switch persona without any retraining.
```

### PersonaPlex microservice architecture

**Stack:** FastAPI, Redis, MongoDB, asyncio

**Core responsibilities:**
- Persona profile management (CRUD in MongoDB)
- Long-term memory persistence (MongoDB cold storage)
- Redis-backed hot context cache (active session window)
- Contextual prompt assembly (<30ms)
- Multilingual personality adaptation via language-aware prompt templates
- Emotional state tracking and evolution
- Session continuity across reconnections
- Memory summarization workers (background)

**Session model:**
```json
{
  "session_id": "uuid",
  "user_id": "uuid",
  "persona_id": "aziza_ru|aziza_uz|aziza_en",
  "language": "ru|uz-latn|uz-cyrl|en",
  "emotion_state": "neutral|warm|curious|empathetic",
  "conversation_summary": "...",
  "active_context_window": [],
  "memory_refs": ["mongo_ref_1", "mongo_ref_2"]
}
```

**Multilingual persona prompts (language-adaptive):**
```python
PERSONA_TEMPLATES = {
    "ru": "Ты Азиза — тёплый, умный AI-помощник. Говори естественно по-русски...",
    "uz-latn": "Siz Aziza — mehribon, aqlli AI yordamchisiz. O'zbek tilida...",
    "uz-cyrl": "Сиз Азиза — меҳрибон, ақлли AI ёрдамчисисиз...",
    "en": "You are Aziza — a warm, intelligent AI assistant..."
}
```

**Redis memory strategy:**

Hot cache (Redis) — expires with session:
```
persona:context:{session_id}   → assembled prompt (injected per step)
persona:state:{session_id}     → emotion_state, language, persona_id
persona:window:{session_id}    → last N conversation turns
```

Cold storage (MongoDB) — persists indefinitely:
```
conversations collection       → full history per user
memories collection            → summarized long-term memory
personas collection            → persona profiles
```

### PersonaPlex APIs

```
POST /persona/load     → Load persona for session, seed Redis hot cache
POST /persona/switch   → Swap persona mid-session (language or character change)
GET  /persona/state    → Current persona state for session
POST /memory/store     → Persist conversation turn to MongoDB
POST /memory/retrieve  → Fetch relevant memories for context assembly
POST /prompt/build     → Assemble full context prompt (<30ms SLA)
```

### Deliverables
- Deployed PersonaPlex FastAPI microservice (isolated container)
- Language-adaptive persona prompt templates (RU, UZ-Latn, UZ-Cyrl, EN)
- Redis hot cache + MongoDB cold storage fully operational
- Memory summarization background worker
- Context injection middleware wired to Moshi workers

### Validation checklist
- [ ] Persona loads and injects context in <30ms
- [ ] Persona persists across session reconnections
- [ ] Language switching works without restarting session
- [ ] Emotional state evolves naturally across conversation
- [ ] Memory summarization runs without blocking inference
- [ ] PersonaPlex NOT accessible externally (internal network only)

---

## PHASE 7 — AI ORCHESTRATOR 🔄 REVISED

**Goal:** Coordinate all runtime services and manage GPU worker pool.

**Key revision from original plan:**
Orchestrator manages a **pool of single-session workers**, not a scheduler
that assigns multiple sessions to one worker. Core responsibility is:
"Which worker is free? Route this session to it."

### Worker pool model

```python
WORKER_REGISTRY = {
    "worker-01": { "status": "idle|busy", "session_id": None, "gpu": "0" },
    "worker-02": { "status": "idle|busy", "session_id": None, "gpu": "1" },
    ...
}
```

**Session routing flow:**
```
1. Client requests new session
2. Orchestrator checks WORKER_REGISTRY for idle worker
3. If idle worker found:
     - Mark worker as busy, bind session_id
     - Return worker WebSocket URL to API Gateway
4. If no idle worker:
     - Return 503 with queue position or retry-after header
5. On session end:
     - Worker signals completion to Orchestrator via Redis
     - Orchestrator marks worker idle
     - Next queued session assigned
```

### Tasks

**Orchestration service (Python + asyncio + Redis):**
- Worker registry with heartbeat monitoring
- Session routing: idle worker selection (round-robin or least-recently-used)
- Session binding: 1 session ↔ 1 worker at all times
- Worker heartbeat: workers publish `heartbeat:{worker_id}` every 5s to Redis
- Stale worker detection: remove workers silent >15s from registry
- Session failover: if worker dies mid-session, attempt re-routing to new worker

**Redis pub/sub coordination:**
```
orchestrator:worker:register   → worker announces itself on startup
orchestrator:worker:heartbeat  → per-worker keepalive
orchestrator:session:assign    → orchestrator assigns session to worker
orchestrator:session:release   → worker signals session complete
orchestrator:queue             → pending sessions waiting for free worker
```

**Service discovery:**
- Workers self-register on startup via Redis pub/sub
- Orchestrator maintains live registry, no hardcoded worker list
- Supports dynamic horizontal scaling: add workers at runtime

**Failover handling:**
- Worker crash detected via heartbeat timeout
- Active session flagged, client notified via API Gateway
- Session state retrieved from PersonaPlex (Redis hot cache) for potential re-assignment
- New worker assigned if available

### Deliverables
- Orchestration service with worker pool registry
- Session routing with worker binding
- Dynamic worker discovery (no hardcoded worker count)
- Failover and queue handling

### Validation checklist
- [ ] Sessions route only to idle workers
- [ ] max_sessions=1 enforced per worker
- [ ] Worker crash detected within 15s via heartbeat timeout
- [ ] Sessions queue correctly when all workers busy
- [ ] New workers self-register without orchestrator restart
- [ ] No cross-session state leakage between workers

---

## PHASE 8 — FRONTEND INTEGRATION ✅ COMPLETE

**Goal:** Connect backend to existing Next.js/React frontend.

**Completed deliverables:**
- WebSocket stream connection
- Auth system integration (JWT)
- Streaming controls (start/stop)
- Reconnect logic with exponential backoff
- Event synchronization
- Session state syncing

**Note for revised architecture:**
Frontend must handle the updated session response format:
```json
{
  "session_id": "uuid",
  "worker_ws_url": "wss://worker-01.aziza.internal/stream",
  "persona": { "id": "aziza_ru", "language": "ru" }
}
```
The WebSocket connection goes directly to the assigned worker URL, not a generic endpoint.
Verify frontend reconnect logic re-queries the session endpoint (not a hardcoded worker URL)
so reconnects can be assigned to a different worker if needed.

---

## PHASE 9 — TELEPHONY INTEGRATION 🟡 PENDING

**Goal:** Enable AI voice calls through telephony infrastructure.

**Architecture note:**
Each inbound call maps to exactly one GPU worker session (same 1-session-per-worker model).
The telephony bridge is a separate service that converts RTP audio to WebSocket audio
before forwarding to the Moshi worker.

### Tasks

**Asterisk ARI integration:**
- Connect to Asterisk via ARI (Asterisk REST Interface) WebSocket
- Handle inbound call events: `StasisStart`, `StasisEnd`, `ChannelDtmfReceived`
- Build call lifecycle management: answer, hold, transfer, hangup

**RTP bridge:**
```
PSTN call → Asterisk → RTP stream
RTP stream → Bridge service (FFmpeg/GStreamer) → WebSocket audio chunks
WebSocket audio → API Gateway → Orchestrator → GPU Worker
```

**Session lifecycle for telephony calls:**
```python
# On inbound call:
call_id = event["channel"]["id"]
session = await api_gateway.create_session(caller_id=call_id)
worker_ws = session["worker_ws_url"]
bridge = RTPBridge(rtp_port=..., worker_ws=worker_ws)
await bridge.start()

# On call end:
await bridge.stop()
await api_gateway.release_session(session["session_id"])
```

**SIP handling:**
- SIP trunk configuration in Asterisk
- Inbound DID routing to Aziza ARI application
- DTMF support for menu navigation (optional)

**Recording controls:**
- Per-call recording toggle via ARI
- Audio stored in MongoDB (reference only, not model input)

**Reconnect handling:**
- If GPU worker dies mid-call, attempt session reassignment within 2s
- If reassignment fails, play hold music and retry
- Maximum retry: 3 attempts before graceful call termination

### Deliverables
- Telephony ARI service (Python + asyncio)
- RTP → WebSocket audio bridge (FFmpeg pipeline)
- Call lifecycle management
- SIP trunk integration
- End-to-end telephony test (real phone call → AI response)

### Validation checklist
- [ ] Inbound call connects to GPU worker within 3s
- [ ] RTP audio converted and streamed without desync
- [ ] TTFT on telephony path <200ms (100ms inference + ~100ms bridge overhead)
- [ ] Call ends cleanly, worker released to pool
- [ ] Worker failure during call triggers reassignment attempt
- [ ] No RTP packet loss causing audio gaps

---

## PHASE 10 — MONITORING & OBSERVABILITY 🟡 PENDING

**Goal:** Production-grade monitoring for the entire platform.

**Key additions vs original plan:**
Monitoring must be worker-aware — metrics tracked per-worker, not just globally.
Worker pool utilization is the primary operational dashboard.

### Tasks

**Prometheus metrics:**
- Per-worker: GPU memory usage, TTFT, inter-token latency, session count (always 0 or 1)
- Worker pool: idle workers, busy workers, queue depth
- PersonaPlex: prompt assembly latency, cache hit rate, memory retrieval time
- API Gateway: WebSocket connections, session creation rate, auth failures
- Redis: pub/sub message rate, queue depths, memory usage
- Telephony: active calls, RTP bridge latency, call failure rate

**Grafana dashboards:**

Dashboard 1 — Worker Pool Health:
- Grid of worker cards (idle=green, busy=amber, offline=red)
- Queue depth over time
- Session throughput (sessions completed per hour)

Dashboard 2 — Latency:
- TTFT per worker (heatmap)
- E2E latency distribution (p50, p95, p99)
- PersonaPlex overhead distribution

Dashboard 3 — GPU:
- VRAM usage per worker
- GPU utilization % per worker
- CUDA errors (should be 0)

Dashboard 4 — Telephony:
- Active calls
- RTP bridge latency
- Call completion rate

**Loki log aggregation:**
- All service logs indexed by: service, session_id, worker_id
- CUDA error alerts → immediate PagerDuty/Slack notification
- TTFT breach alert (>150ms) → log warning with session context

**Alerting rules:**
```yaml
- alert: WorkerPoolExhausted
  expr: aziza_workers_idle == 0
  for: 30s
  severity: warning

- alert: HighTTFT
  expr: aziza_ttft_p95 > 150
  for: 60s
  severity: warning

- alert: CUDAError
  expr: increase(aziza_cuda_errors_total[5m]) > 0
  severity: critical

- alert: PersonaPlexSlow
  expr: aziza_persona_prompt_build_p99 > 50
  for: 60s
  severity: warning
```

### Deliverables
- Prometheus + Grafana + Loki stack deployed
- Worker-aware dashboards
- Alerting rules configured
- GPU per-worker monitoring

### Validation checklist
- [ ] All worker metrics visible in Grafana
- [ ] TTFT dashboard shows real latency per worker
- [ ] Worker pool utilization dashboard live
- [ ] CUDA error alert fires on test injection
- [ ] PersonaPlex latency tracked and within SLA

---

## PHASE 11 — MULTILINGUAL FINE-TUNING 🔴 HIGH PRIORITY

**Status:** Begin immediately (Phase 1 budget credited to this phase)

**Goal:** Train QLoRA adapter for natural Russian and Uzbek speech on Moshi.

**Critical architectural note:**
Fine-tuning covers ONLY phonetics and language fluency (text projection + audio codebooks).
Personality and manner of speech are controlled by PersonaPlex (Phase 6), NOT baked into weights.
This separation means: one adapter, many personalities — no retraining per persona.

### Step 1 — Tokenizer Audit

Before any training, audit Moshi's tokenizer for Cyrillic and Uzbek Latin coverage:

```python
from moshi.tokenizer import MoshiTokenizer
tok = MoshiTokenizer.load()

test_tokens = {
    "ru": "Привет, меня зовут Азиза. Как я могу помочь?",
    "uz-latn": "Salom, mening ismim Aziza. Qanday yordam bera olaman?",
    "uz-cyrl": "Салом, менинг исмим Азиза. Қандай ёрдам бера оламан?"
}

for lang, text in test_tokens.items():
    tokens = tok.encode(text)
    decoded = tok.decode(tokens)
    coverage = len([t for t in tokens if t < tok.vocab_size]) / len(tokens)
    print(f"{lang}: {coverage:.1%} coverage, roundtrip: {text == decoded}")
```

**If coverage < 90% for any language:** Extend tokenizer vocab with target language characters.
Do NOT proceed to training with poor tokenizer coverage — this is the most common
cause of garbled output in multilingual fine-tuning.

**Uzbek-specific note:**
Uzbek Latin uses characters not present in standard Latin (Oʻ, Gʻ, Sh, Ch, Ng).
Uzbek Cyrillic shares most chars with Russian Cyrillic but with additions (Ҳ, Ҷ, Қ, Ғ, Ў).
Verify each of these is tokenized correctly, not split into byte-level fallbacks.

### Step 2 — Dataset Preparation

**Format:** Instruction/dialogue format for SFT (supervised fine-tuning):
```json
{
  "instruction": "Respond naturally in Russian as a warm, helpful assistant.",
  "input": "Расскажи мне о погоде сегодня.",
  "output": "Сегодня погода довольно приятная — солнечно с лёгким ветерком..."
}
```

**Dataset requirements:**
- Russian: minimum 5,000 dialogue pairs, preferably conversational (not formal)
- Uzbek Latin: minimum 3,000 dialogue pairs
- Uzbek Cyrillic: minimum 3,000 dialogue pairs (can translate from Latin with script conversion)
- English: 2,000 pairs (Moshi already handles English, minimal fine-tuning needed)

**Data quality checklist:**
- [ ] No machine-translated artifacts (check for literal translation patterns)
- [ ] Conversational register (not formal/legal/academic)
- [ ] Short to medium responses (voice-first: 1–4 sentences per turn)
- [ ] Audio phonetic pairs where available (preferred for codebook training)
- [ ] Remove any personally identifiable information

**Script to prepare dataset:**
```python
import json
from datasets import Dataset

def prepare_moshi_dataset(raw_data: list[dict]) -> Dataset:
    formatted = []
    for item in raw_data:
        formatted.append({
            "text": f"### Instruction:\n{item['instruction']}\n\n"
                    f"### Input:\n{item['input']}\n\n"
                    f"### Response:\n{item['output']}"
        })
    return Dataset.from_list(formatted)
```

### Step 3 — QLoRA Training Configuration

**Hardware:** Single H100 SXM 80GB
**Budget:** 2 days of H100 time (~48 hours total including prep and evaluation)
**Estimated training time:** 2–5 hours for full run

**LoRA configuration:**
```python
from peft import LoraConfig, TaskType

peft_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    # Text projection layers + output norm only
    # Do NOT target audio codebook layers in first run — validate text first
    target_modules=["linear_in", "linear_out", "text_emb", "out_norm"],
    bias="none"
)
```

**Training arguments:**
```python
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./aziza-multilingual-adapter",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    fp16=True,                    # H100 supports bf16; use bf16=True if available
    warmup_ratio=0.03,
    lr_scheduler_type="cosine",
    save_steps=100,
    logging_steps=10,
    evaluation_strategy="steps",
    eval_steps=100,
    load_best_model_at_end=True,
    dataloader_num_workers=4,
    report_to="none"              # Add wandb if tracking is desired
)
```

**QLoRA quantization (memory efficiency on H100):**
```python
from transformers import BitsAndBytesConfig
import torch

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)
```

**Two-pass training strategy:**
1. Pass 1 — Text layers only (`linear_in`, `linear_out`, `text_emb`, `out_norm`)
   - Validate: can the model produce coherent Russian/Uzbek text?
2. Pass 2 (if needed) — Add audio codebook layers
   - Validate: does pronunciation improve naturally?

### Step 4 — Evaluation

**Automated metrics:**
- BLEU score per language against held-out test set
- Perplexity on validation split
- Streaming latency with adapter loaded (must remain <100ms TTFT)

**Manual evaluation checklist (per language):**
- [ ] Russian: natural conversational tone, no literal translation artifacts
- [ ] Uzbek Latin: correct script, correct phoneme production
- [ ] Uzbek Cyrillic: correct script, distinct from Russian where applicable
- [ ] English: no regression from base Moshi quality
- [ ] Voice-first response length: responses are concise and natural when spoken
- [ ] No hallucinated language mixing (Russian mid-Uzbek sentence or vice versa)

**Latency regression test (critical):**
```python
# Run this before and after adapter loading
import time

def benchmark_ttft(engine, test_audio, n=20):
    latencies = []
    for _ in range(n):
        start = time.perf_counter()
        engine.step(test_audio)
        latencies.append((time.perf_counter() - start) * 1000)
    print(f"TTFT p50: {sorted(latencies)[10]:.1f}ms")
    print(f"TTFT p95: {sorted(latencies)[19]:.1f}ms")
```

Adapter must add <10ms overhead. If TTFT exceeds 110ms with adapter, reduce adapter rank.

### Step 5 — PersonaPlex Integration

After adapter is validated:
1. Load base Moshi + QLoRA adapter on worker containers
2. Confirm PersonaPlex prompt injection still works with adapter loaded
3. Test language switching mid-session (PersonaPlex changes language context, adapter handles phonetics)
4. Validate: Russian session → PersonaPlex injects RU persona → model responds in natural Russian

### Deliverables
- Tokenizer audit report with coverage percentages per language
- Prepared and formatted dataset (train/val/test split)
- Trained QLoRA adapter (LoRA r=16, <50MB file)
- Training logs + evaluation results
- Latency benchmark: before/after adapter (must show <10ms overhead)
- Integration test: adapter + PersonaPlex live session

### Validation checklist
- [ ] Tokenizer coverage >95% for all target languages
- [ ] Training loss converges without instability
- [ ] Russian responses: natural, conversational, no translation artifacts
- [ ] Uzbek Latin responses: correct phonemes and script
- [ ] Uzbek Cyrillic responses: correct script, distinct characters preserved
- [ ] TTFT regression <10ms with adapter loaded
- [ ] Streaming stability: no mid-sentence gaps introduced by adapter
- [ ] PersonaPlex personality injection works correctly with adapter
- [ ] Adapter file size <100MB

---

## REDIS MEMORY STRATEGY (FINAL)

**Hot cache (Redis) — session-scoped, expires on session end:**
```
persona:context:{session_id}   → assembled prompt string (refreshed per turn)
persona:state:{session_id}     → JSON: emotion_state, language, persona_id
persona:window:{session_id}    → list: last 10 conversation turns
audio:in:{session_id}          → incoming audio chunks queue
audio:out:{session_id}         → outgoing audio chunks queue
worker:session:{worker_id}     → currently active session_id (or null)
```

**Cold storage (MongoDB) — persistent:**
```
users               → user profiles, preferences
sessions            → session metadata and history
conversations       → full conversation logs per session
memories            → summarized long-term memory per user
personas            → persona definitions and configurations
adapters            → fine-tuned adapter metadata and paths
```

---

## SECURITY REQUIREMENTS (ALL PHASES)

- JWT authentication on all external endpoints
- HTTPS/WSS for all external communication
- Redis and MongoDB require auth credentials (never default/blank)
- PersonaPlex, Moshi workers, Orchestrator — internal network only, NOT publicly exposed
- Only API Gateway is exposed publicly
- All secrets via environment variables, never hardcoded
- Worker-to-Orchestrator communication via internal Redis, never public
- Telephony ARI endpoint: internal only, behind NGINX with IP allowlist

---

## DEPLOYMENT ORDER (ENFORCED)

```
Phase 1 (Infrastructure) → complete ✅
Phase 2 (API Gateway)    → complete ✅
Phase 3 (Streaming)      → complete ✅
Phase 11 (Fine-Tuning)   → START NOW (parallel to Phase 4-7 infrastructure work)
Phase 4 (Moshi Runtime)  → build while datasets are being prepared
Phase 5 (Integration)    → after Phase 4 + Phase 11 adapter ready
Phase 6 (PersonaPlex)    → after Phase 5 E2E validated
Phase 7 (Orchestrator)   → after Phase 6
Phase 8 (Frontend)       → complete ✅
Phase 9 (Telephony)      → after Phase 7
Phase 10 (Monitoring)    → after Phase 9
```

**Phase 11 can run in parallel:** Dataset prep and training happen independently.
The adapter is a file that gets loaded into Phase 4 workers once ready.
Do not block Phase 4-7 development on Phase 11 completion.

---

*AZIZA Platform — Revised Build Plan v2.0*
*Architecture locked: 1 session per GPU worker, horizontal scaling, PersonaPlex as dynamic injection layer*
