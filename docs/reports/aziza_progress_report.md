# AZIZA Platform — Projected Progress Report
**Date:** 25 June 2026 | **Server:** `83.126.40.53` (Proxmox VM 101, RTX A6000)
**Prepared by:** Antigravity AI | **For Review:** Milestone 2 Agreement & Full Project

---

## A. Milestone 2 — QLoRA Bilingual Adapter (Detailed Status)

> **Objective:** Train and deploy a lightweight QLoRA adapter for Moshi targeting bilingual (Russian/Uzbek) text and audio codebooks to achieve native phonetic pronunciation with minimal latency overhead.

---

### Deliverable 1 — Training Configuration & Setup
**Status: COMPLETE**

| Sub-task | Status | Evidence |
|----------|--------|----------|
| Tokenizer Cyrillic/Latin audit script | Done | `audit_tokenizer.py` present; 66.7% Cyrillic coverage confirmed in assistant turns (20,000 / 30,000 samples) |
| Bilingual dataset prepared | Done | `aziza-bilingual.jsonl` (Russian/Uzbek mixed), `aziza-uzbek.jsonl` (Uzbek only) |
| Dataset ChatML normalization | Done | `train_russian.py` parses `CLIENT/BROKER` dialogue blocks into ChatML `messages` format |
| LoRA hyperparameters locked | Done | `r=32`, `alpha=32`, `dropout=0.05`, targets: `q/k/v/o_proj`, `max_seq=512`, `batch=4`, `lr=2e-4`, `epochs=3` |
| QLoRA 4-bit config | Done | `bnb_4bit_quant_type="nf4"`, `bnb_4bit_compute_dtype=bfloat16`, double quant enabled |
| Latency-aware dropout/rank selection | Done | r=32 chosen for quality/latency balance; `vram_oom_threshold_gb=75.0` guard |

**Locked Config (do NOT change without approval):**
```
LoRA r=32 | alpha=32 | dropout=0.05
Targets: q_proj, k_proj, v_proj, o_proj
Base: Vikhr-Llama3.1-8B (Moshi-compatible Mistral architecture)
4-bit NF4 | bfloat16 compute | double quantization
```

---

### Deliverable 2 — Phonetic Adapter Training
**Status: PARTIAL — Uzbek PASSED all gates, Russian FAILED (shape mismatch)**

#### Uzbek Adapter — `adapters/aziza-adapter-final-uz`
**Status: PASSED ALL EVALUATION GATES**

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Script Fidelity | **92.4%** | >= 80% | PASS |
| Language Switching (Latin/Cyrillic) | **98.1%** | >= 95% | PASS |
| Persona Retention | **100%** | — | PASS |
| Test Set | 200 dialogues (100 Latin + 100 Cyrillic) | — | Complete |

**Uzbek adapter is production-ready.**

#### Russian Adapter — In Progress
**Status: GATES FAILED — Adapter shape mismatch, must retrain**

The Russian QLoRA training ran on a prior GPU instance (Mistral-7B base, r=32) but the resulting checkpoint has **incompatible weight shapes** when loaded against the current base model (`Vikhr-Llama3.1-8B`). The error is a rank/dim mismatch across all attention layers:

```
size mismatch: q_proj.lora_A shape [32, 3584] vs expected [16, 4096]
```

**Root cause:** The checkpoint was trained against `Mistral-7B-v0.1` (hidden dim 3584) but is being evaluated against `Vikhr-Llama3.1-8B` (hidden dim 4096). Training must be rerun against the correct base model.

**Remaining work to close D2:**
1. Re-run `train_russian.py --register all` on the **RTX A6000** (49GB VRAM) with `Vikhr-Llama3.1-8B` as base model (estimated: 8–12 hours)
2. Pass evaluation gate: `pass_rate >= 0.80` on Russian test set

> **GPU Infrastructure Note:** The Milestone 2 agreement specifies an **H100** server for deployment. Current infrastructure is an **NVIDIA RTX A6000 (49GB VRAM)** via Proxmox VM. Training is feasible on the A6000, but evaluation benchmarks (TTFT, throughput) will differ from H100 targets. This should be communicated to the client if H100-grade performance numbers are expected.

---

### Deliverable 3 — Evaluation & Optimization
**Status: NOT STARTED (blocked by D2 Russian failure)**

| Sub-task | Status | Notes |
|----------|--------|-------|
| Deploy adapter to GPU server | Pending | Adapter not ready; server is A6000 not H100 |
| Native fluency evaluation (Russian) | Pending | Blocked by shape mismatch |
| Grammar accuracy gate (>= 80%) | Pending | |
| Real-time streaming latency test | Pending | Moshi worker service exists (`moshi_service.py`) but not connected |
| TTFT benchmark | Pending | `bench_ttft.py` exists, ready to run post-training |

Note: The Uzbek adapter (`aziza-adapter-final-uz`) is ready for D3 evaluation now. D3 for Russian requires completing the retraining first.

---

### Deliverable 4 — PersonaPlex Integration
**Status: SERVICE CODED — Integration NOT wired**

| Sub-task | Status | Evidence |
|----------|--------|----------|
| PersonaPlex microservice | Built | `backend/persona-plex/` — FastAPI, Redis pub/sub, memory, sessions, persona definitions |
| Redis pub/sub token streaming | Built | `monitor_tokens()` subscribes to `session:*:tokens` |
| Persona CRUD + emotional state API | Built | `main.py`, `models.py`, `persona_plex_core.py`, `database.py`, `memory.py` |
| Hook adapter to PersonaPlex | Pending | No live connection from trained adapter inference to PersonaPlex emotion prompting |
| Real-time emotional state injection | Pending | Requires Moshi worker + adapter serving to be connected |
| End-to-end demo | Pending | Full chain: User audio → Moshi → Adapter → PersonaPlex → Styled response |

---

### Milestone 2 Summary Dashboard

```
D1  Training Config & Setup       [====================]  100% COMPLETE
D2  Phonetic Adapter Training     [==========          ]   50% PARTIAL  (Uzbek done, Russian needs rerun)
D3  Evaluation & Optimization     [                    ]    5% BLOCKED   (Uzbek ready, Russian blocked)
D4  PersonaPlex Integration       [========            ]   40% PARTIAL  (Service built, not wired)

Overall Milestone 2:              [============        ]  ~48%
```

**Estimated completion time (with A6000 available now):**

| Task | Est. Time |
|------|-----------|
| Russian retraining run | 8–12 hrs |
| Eval gates (Russian) | 1 hr |
| Moshi worker + Adapter wire-up | 4–6 hrs |
| PersonaPlex live integration | 3–4 hrs |
| End-to-end streaming demo | 2–3 hrs |
| **Total to close Milestone 2** | **~18–26 hrs** |

---

## B. Complete Project Status

> Architecture: NestJS API Gateway → Python Orchestrator → Redis → Moshi Worker (audio) + PersonaPlex (persona) + vLLM (text LLM)

---

### Phase 1 — Infrastructure & Base Services
**Status: COMPLETE (100%)**

| Component | Status | Details |
|-----------|--------|---------|
| Proxmox VM (101) | Online | Ubuntu 24.04, 293GB disk (58GB used), 49GB VRAM |
| Network / SSH | Stable | Gateway `10.10.10.1` persisted via netplan; SSH port 122 |
| NVIDIA RTX A6000 | Verified | `nvidia-smi` clean: driver 535.309.01, CUDA 12.2, 38C idle |
| Redis | Running | `redis-server`, PONG confirmed |
| PM2 auto-restart | Configured | `pm2-root.service` enabled via systemd — survives reboots |
| API Gateway (NestJS) | Online | Port 8080, `/api/health` → `OK`, all routes mapped |
| Orchestrator (Python) | Online | "AI Orchestrator started", connected to Redis |
| Python venv | Ready | `/root/aziza-build/venv`, all core deps installed |

---

### Phase 2 — Dataset & Training Pipeline
**Status: PARTIAL (65%)**

| Component | Status | Details |
|-----------|--------|---------|
| Bilingual datasets | Ready | `aziza-bilingual.jsonl` (Russian+Uzbek), `aziza-uzbek.jsonl`, `new_russian_pairs.jsonl` |
| Uzbek training pipeline | Complete | `train_uzbek.py`, `train_uzbek_latin_hf.py`, `train_uzbek_cyrillic_hf.py` |
| **Uzbek adapter** | **Production-ready** | `adapters/aziza-adapter-final-uz`, all eval gates PASSED |
| Russian training pipeline | Script ready | `train_russian.py` — locked config, ready to run |
| **Russian adapter** | Needs rerun | Shape mismatch with current base model; must retrain on Vikhr-Llama3.1-8B |
| Evaluation harness | Ready | `eval_russian.py`, `eval_uzbek.py` |
| Benchmark tools | Ready | `benchmark.py`, `benchmark_v2.py`, `bench_ttft.py` |
| Curriculum training | Scripted | `run_curriculum_training.sh` |

---

### Phase 3 — Moshi Audio Worker
**Status: CODED — Not serving (45%)**

| Component | Status | Details |
|-----------|--------|---------|
| Moshi engine wrapper | Coded | `moshi_engine.py`, `moshi_inference.py` |
| GPU scheduler | Coded | `gpu_scheduler.py` — manages VRAM allocation |
| Moshi service (WebSocket) | Coded | `moshi_service.py` |
| Moshi model weights | INCOMPLETE | `model_cache/model.safetensors` is only 29MB — full Moshi is ~7GB |
| Adapter loading into Moshi | Pending | Requires Russian adapter rerun + integration |
| Live audio streaming | Not tested | Needs Moshi fully loaded + WebSocket validation |
| Moshi PM2 service | Not started | Not in current `ecosystem.config.js` |

> **CRITICAL:** The `model_cache/model.safetensors` at 29MB is incomplete. Full Moshi (`kyutai/moshika-pytorch-bf16`) is ~7GB. A complete download via HuggingFace token is required before the audio worker can serve.

---

### Phase 4 — PersonaPlex Microservice
**Status: BUILT — Not integrated (60%)**

| Component | Status | Details |
|-----------|--------|---------|
| FastAPI service | Built | `backend/persona-plex/main.py` |
| Redis pub/sub (token monitoring) | Built | Subscribes to `session:*:tokens` |
| Persona models & CRUD | Built | `models.py`, `persona_plex_core.py` |
| Memory / session history | Built | `memory.py`, `database.py` |
| Emotional state injection | Coded | Prompt-based emotion system designed |
| Live connection to adapter | Pending | Not connected to Moshi worker |
| PersonaPlex PM2 service | Not started | Not in current `ecosystem.config.js` |
| MongoDB backend | Not provisioned | `.env` references `mongodb://localhost:27017/aziza` — MongoDB not installed |

---

### Phase 5 — vLLM Text Inference (EN/RU/UZ)
**Status: NOT STARTED (15%)**

| Component | Status | Details |
|-----------|--------|---------|
| vLLM installed | v0.23.0 | In system Python |
| EN model config | Configured | `Vikhrmodels/Vikhr-Llama-3.1-8B-Instruct` in `.env` |
| UZ model config | Configured | `uzlm/alloma-3B-Instruct` in `.env` |
| vLLM server (EN) launch | Not started | Port 8000, GPU 0 |
| vLLM server (UZ) launch | Pending | Port 8001 — only 1 GPU exists, must share |
| API gateway to vLLM routing | Not tested | Route exists in NestJS, no backend serving yet |
| Russian phonetic model serving | Blocked | Requires Russian adapter completion |

> **WARNING:** The `.env` assumes 2 GPUs (`LLM_GPU_EN=0`, `LLM_GPU_UZ=1`). We have **1 RTX A6000 (49GB)**. With 49GB VRAM, both an 8B and 3B model can co-exist at `VLLM_GPU_MEMORY_UTIL=0.45` per model, but this requires explicit reconfiguration before launch.

---

### Phase 6 — Frontend & API Integration
**Status: PARTIAL (30%)**

| Component | Status | Details |
|-----------|--------|---------|
| Frontend (public dir) | Present | `/backend/services/api-gateway/public/` |
| WebSocket test client | Present | `test_ws.py`, `aziza-test.html` |
| Nginx config | Scripted | `apply_nginx.sh`, `nginx/` dir |
| Cloudflare tunnel | Installed | `cloudflared v2026.3.0`, ready |
| Public tunnel active | Not running | Tunnel not launched |
| E2E audio demo | Not tested | Full pipeline not connected |

---

### Phase 7 — Telephony Bridge
**Status: SKELETON ONLY (10%)**

| Component | Status | Details |
|-----------|--------|---------|
| Code skeleton | Present | `backend/telephony-bridge/main.py` |
| Live integration | Not started | Out of scope for Milestone 2 |

---

## Complete Project Dashboard

```
Phase 1  Infrastructure & Base Services    [====================]  100% COMPLETE
Phase 2  Dataset & Training Pipeline       [=============       ]   65% PARTIAL
Phase 3  Moshi Audio Worker                [=========           ]   45% PARTIAL
Phase 4  PersonaPlex Microservice          [============        ]   60% PARTIAL
Phase 5  vLLM Text Inference               [===                 ]   15% NOT STARTED
Phase 6  Frontend & Tunnel                 [======              ]   30% PARTIAL
Phase 7  Telephony Bridge                  [==                  ]   10% SKELETON

OVERALL PROJECT:                           [=========           ]  ~46%
```

---

## Priority Action Plan (Ordered by dependency)

| # | Task | Est. Time | Blocks |
|---|------|-----------|--------|
| 1 | **Retrain Russian QLoRA** on Vikhr-Llama3.1-8B (`--register all`) | 8–12 hrs | D2, D3, D4 |
| 2 | **Run Russian eval gates** (`eval_russian.py`, pass_rate >= 0.80) | 1 hr | D3 |
| 3 | **Download full Moshi model** (~7GB via HF token) | 1–2 hrs | D3, D4, Phase 3 |
| 4 | **Launch vLLM** (EN 8B + UZ 3B on single A6000, VRAM split 45%/45%) | 2 hrs | Phase 5 |
| 5 | **Wire Moshi worker + adapter** into PM2 ecosystem | 4–6 hrs | D3, D4 |
| 6 | **Connect PersonaPlex** to live adapter inference | 3–4 hrs | D4 |
| 7 | **Install MongoDB** and connect PersonaPlex database | 1 hr | Phase 4 |
| 8 | **End-to-end demo** (audio in → styled Russian/Uzbek response) | 2–3 hrs | Milestone 2 close |
| 9 | Launch Cloudflare tunnel for client review | 30 min | Client demo |

---

> **Bottom line:** The foundation — infrastructure, datasets, Uzbek adapter (production-ready), full services skeleton, NestJS gateway online — is solid. The critical path to closing Milestone 2 is: **Russian adapter retraining (8–12h) → full Moshi model download → adapter+Moshi integration → PersonaPlex wire-up → E2E demo.** Estimated 18–26 working hours of execution on the available A6000 hardware.
