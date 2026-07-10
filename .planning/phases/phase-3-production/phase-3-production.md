# Phase 3 — Production Infrastructure & Hardening
> Derived from AI-SPEC-Aziza.md. Scope: harden all three modes (text-to-text, voice-to-text,
> voice-to-voice) for production traffic on Proxmox-hosted infrastructure, including telephony
> integration for voice-to-voice. Prerequisite: Phase 1 (stable core) and Phase 2 (adapters) complete.

---

## Goal
Move Aziza from "working on a test VM" to a production-ready deployment: proper process supervision,
SSL/routing, observability, concurrency handling across all modes, and (for voice-to-voice) Asterisk ARI
telephony.

---

## Critical Failure Modes In Scope

1. **Single-worker starvation (voice-to-voice)** — concurrent WebSocket connections assigned to the same
   GPU worker → OOM, crash, no graceful 503.
2. **Orchestrator crash loop** — recurs under production load if the Enum-serialization fix from Phase 1
   isn't holding up; needs load-test coverage here.
3. **Disk pressure** — model artifacts, logs, and fine-tuned adapters accumulate; needs an ongoing guard,
   not just a one-time check.
4. **No external-facing routing** — Nginx config from Phase 1 was internal-testing-only; this phase needs
   SSL termination and multi-upstream routing suitable for real traffic (and SIP/PSTN via Asterisk).

---

## Tasks

| Task | File | Status |
|---|---|---|
| `POST /session/create` endpoint with `mode` field (text / voice_to_text / voice_to_voice) | `api-gateway/src/session/` | |
| `POST /session/:id/persona` hot-swap, shared across modes | `api-gateway/src/session/` | |
| Text-engine wrapper around Ollama `/api/chat` | `text-engine/` | |
| ASR-to-text-engine handoff (transcript normalization step) | `asr-service/` + `text-engine/` | |
| GPU middleware `/health`, `/session/assign`, `/adapter/load` | `gpu-middleware/main.py` | |
| GPU middleware Prometheus `/metrics` endpoint | `gpu-middleware/main.py` | |
| Context injection WebSocket handler (puppeteer, voice-to-voice) | `voice.gateway.ts` + `moshi_service.py` | |
| Nginx SSL config (gateway + ASR + voice upstreams) | `/etc/nginx/sites-enabled/aziza` | |
| Systemd/PM2 service files for Ollama, ASR, gateway, personaplex | `/etc/systemd/system/` or `pm2 ecosystem.config.js` | |
| Prometheus + Grafana dashboards (per-mode panels) | `monitoring/` | |
| E2E tests across all 3 modes, including mode-switch scenarios | `tests/e2e/` | |
| Asterisk ARI telephony bridge (voice-to-voice) | `<!-- TODO: file path once telephony service is scaffolded -->` | |

---

## Implementation Notes

### Multi-Worker / Concurrency Guard (voice-to-voice)
Each concurrent session must be assigned to a worker with available VRAM headroom — not just round-robin
onto whatever worker is "next." `ServerState.lock` must be held during the full inference step;
concurrent sessions on one worker cause CUDA memory corruption, not just slowness.

```
VRAM per session: ~19GB
OOM threshold: >72GB → mark worker draining, reject new sessions with HTTP 503
```

### Nginx
```
proxy_read_timeout 3600s;   # required for long-lived WebSocket sessions
```
Routes needed: gateway (`8080`), ASR (`8020`), text-engine/Ollama (internal only, `11434`), with SSL
termination at the Nginx layer for all externally-facing routes.

### Shared Session Routing
A shared orchestrator routes each session to one of the three mode handlers based on `mode` in the
session payload. All three modes share Redis-backed session metadata and the persona/system-prompt
layer, so persona consistency must hold across mode switches within a single conversation — this is a
specific thing to load-test in this phase (not just per-mode correctness).

---

## Evaluation Strategy

| Dimension | Rubric | Measurement Approach | Priority | Mode(s) |
|---|---|---|---|---|---|
| **Session isolation** | Session A's state never appears in Session B's response | Code: concurrent session test, all 3 modes | Critical | All |
| **OOM guard** | >72GB VRAM → worker marked full, new sessions get 503 | Code: simulated VRAM threshold test | High | Voice-to-voice |
| **Disk guard** | Disk free <15% → block model pulls, alert | Code: scheduled disk check | High | All (shared host) |
| **Persona fidelity across mode switch** | System prompt instructions followed when a conversation switches modes mid-session | LLM Judge: persona adherence rubric | Medium | All |
| **Concurrency under load** | 5+ simultaneous sessions across modes without crash or starvation | Load test | Critical | All |

### Eval Tooling
```bash
pytest tests/test_session_isolation.py -v
python scripts/benchmark_ttft.py --sessions 5         # voice-to-voice, concurrency
python scripts/benchmark_text_latency.py --sessions 5  # text-to-text / voice-to-text, concurrency
```

---

## Guardrails (production-grade, online)

| Guardrail | Trigger | Intervention | Mode |
|---|---|---|---|
| **Ollama health check** | `/api/tags` fails or times out | Mark text-engine `down`, graceful error, alert | Text-to-text, Voice-to-text |
| **VRAM OOM guard** | `nvidia-smi` VRAM >72GB | Mark worker `draining`; reject new sessions with HTTP 503 | Voice-to-voice |
| **Session TTL** | No input for >30s | Close session, release GPU slot | All |
| **Disk guard** | Disk free <15% on `aziza-worker-01` | Block model pulls/fine-tuning, alert | All (shared host) |

## Production Monitoring

```
aziza_ollama_up (gauge)
aziza_text_ttft_seconds (histogram)     — p95 <1s gate
aziza_asr_latency_seconds (histogram)    — p95 <1.5s gate
aziza_ttft_seconds (histogram)           — p95 <250ms gate
aziza_session_active (gauge)             — by mode
aziza_gpu_vram_used_gb (gauge)           — alert >72GB
aziza_disk_free_pct (gauge)              — alert <15%
aziza_session_errors_total (counter)     — by mode
aziza_screech_events_total (counter)
aziza_audio_mean_abs (histogram)
```

**Alert Thresholds**
| Metric | Threshold | Action |
|---|---|---|
| `aziza_ollama_up` | 0 for >60s | Page on-call; restart via PM2/systemd |
| `aziza_ttft_seconds` p95 | >500ms | Page on-call; check CUDA graph + VRAM |
| `aziza_gpu_vram_used_gb` | >72GB | Auto-drain worker; page if all workers drain |
| `aziza_disk_free_pct` | <15% | Block model pulls; page on-call |
| `aziza_screech_events_total` | >3 in 5min | Investigate audio pipeline + model state |
| `aziza_session_errors_total` | >10 in 5min | Check orchestrator + Redis connectivity |

**Smart Sampling**
- Always sample sessions with a screech event or Ollama-down error
- 20% of sessions >5 min, any mode
- 100% of sessions where `screech_detected=True`
- 5% random baseline, all modes

---

## Verification Plan

### Automated Tests
```bash
pytest tests/e2e/ -v                                  # T1-T10 from execution plan
pytest tests/test_session_isolation.py -v
python scripts/benchmark_ttft.py --sessions 5
```

### Manual Verification
- Load test: 5+ concurrent sessions spanning all three modes, confirm graceful 503 (not crash) once
  capacity is exceeded.
- SSL/routing check: hit each public-facing endpoint through Nginx, confirm certs valid and WebSocket
  upgrade succeeds for long-lived sessions.
- Restart drill: kill each supervised service (Ollama, ASR, gateway, personaplex), confirm
  PM2/systemd brings it back without manual steps.
- Telephony smoke test (voice-to-voice via Asterisk ARI), once scaffolded.

---

## Exit Criteria
- [ ] All services under PM2/systemd supervision with confirmed auto-restart
- [ ] Nginx SSL + routing live for all three modes
- [ ] Concurrency test passes: 5+ sessions across modes, graceful 503 under overload, no crash
- [ ] Prometheus + Grafana dashboards live with per-mode panels
- [ ] Persona consistency confirmed across mode switches under load
- [ ] Disk guard enforced (not just monitored)
- [ ] Asterisk ARI telephony bridge functional (voice-to-voice)
- [ ] E2E suite (T1–T10) passing
