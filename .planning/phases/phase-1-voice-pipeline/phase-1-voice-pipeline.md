# Phase 1 — Voice Pipeline & Core Services Unblock
> Derived from AI-SPEC-Aziza.md. Scope: bring all three modes (text-to-text, voice-to-text, voice-to-voice)
> to a working baseline on `aziza-worker-01` and fix the confirmed live blockers.

---

## Goal
Unblock the platform end-to-end: Ollama serving the Vikhr model, the orchestrator stable, Nginx routing
configured, and the voice-to-voice audio pipeline producing clean (non-silent, non-corrupted) audio.

---

## Critical Failure Modes In Scope

1. **Ollama service offline** — `ollama serve` not running/supervised → `ECONNREFUSED` on port `11434`,
   blocking text-to-text and (via handoff) voice-to-text.
2. **Deploy path mismatch** — `deploy_rsync.py` syncs to a path that doesn't match the service's actual
   working directory or systemd/PM2 unit, so deployed code never takes effect.
3. **Missing reverse proxy config** — no Nginx `sites-enabled` entries on `aziza-worker-01` → no SSL
   termination, no consistent routing across gateway/ASR/voice endpoints.
4. **Audio corruption (dtype mismatch)** — int16 PCM not normalized to `[-1,1]` before Mimi encode →
   Moshi generates silence tokens every step. Root cause confirmed in `moshi_engine.py`.
5. **Ghost sessions / GPU leak** — client disconnects without `stop_audio` → moshi-worker holds GPU
   allocation indefinitely, blocking subsequent connections.
6. **Orchestrator crash loop** — `SessionState` Enum serialized as object (not `.value`) → Redis
   `DataError` → orchestrator restarts, dropping all active sessions across all three modes.
7. **Disk pressure** — `aziza-worker-01` at 69% full (~30GB free) as of last audit; needs headroom before
   any model pulls or fine-tuning work in Phase 2.

---

## Tasks

| Task | File | Status |
|---|---|---|
| Bring Ollama service up under PM2/systemd supervision (not ad hoc `&`) | `aziza-worker-01` | |
| Fix `deploy_rsync.py` target path mismatch | `deploy_rsync.py` | |
| Configure Nginx `sites-enabled` for gateway/ASR/voice endpoints | `/etc/nginx/sites-enabled/` | |
| Fix audio normalization (int16 → float32/32768) | `moshi_engine.py:193` | |
| Add diagnostic logging (type/shape/min/max) on audio chunks | `moshi_engine.py:193` | |
| Fix orchestrator `get_or_create` → `ensure_session` | `remote_core.py:137` | |
| Fix Enum serialization bug (`SessionState` → `.value` before Redis write) | orchestrator session module | |
| Verify Redis (6379), ASR (8020), gateway WebSocket (8080) still healthy post-fix | PM2 logs | |
| Check disk space before any further model pulls | `aziza-worker-01` | |
| Add `screech_detector.py` | `moshi-worker/screech_detector.py` | |
| Run mic test → verify `mean_abs` > 0.001 in logs | PM2 logs | |

---

## Implementation Notes

### dtype Guard (voice-to-voice)
`audio_chunk` arrives as `np.int16` from `np.frombuffer()` — must normalize with
`.astype(float32) / 32768.0` before `mimi.encode()`. Do **not** use `np.array(chunk, dtype=float32)`
without normalization.

### Ollama Health
Ollama must be supervised (PM2 or systemd) — a manual `&` background launch will not survive a reboot
or crash, which is the confirmed root cause of the last outage.

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull <vikhr-model-tag>   # TODO: confirm exact tag
# then supervise via PM2 or systemd — do not background manually
```

### Deploy Path Verification
Before assuming a deploy took effect, verify the rsync target path in `deploy_rsync.py` matches the
actual working directory referenced by the PM2/systemd unit for each service.

### Nginx
No `sites-enabled` entries currently exist for `aziza-worker-01`. Without them, gateway/ASR/voice
endpoints are only reachable on raw ports — acceptable for internal testing, not for any external-facing
rollout (including Phase 3 telephony). Minimum config needed this phase: routing to gateway (`8080`),
ASR (`8020`), and Ollama (`11434`, internal only).

---

## Online Guardrails To Implement This Phase

| Guardrail | Trigger | Intervention |
|---|---|---|
| **Ollama health check** | `/api/tags` (or equivalent) fails or times out | Mark text-engine as `down`, return graceful error, alert |
| **Screech detector** | RMS of high-freq band (>8kHz) > threshold for 3 consecutive frames | Reset session, re-inject system prompt, log event |
| **Silence guard** | `mean_abs(audio_np) < 0.0001` for >5 consecutive chunks | Log warning; if >20 chunks, flag session as degraded |
| **Session TTL** | No input received for >30s | Close session, release GPU slot |
| **dtype guard** | `audio_np.dtype != float32` or values outside `[-1.1, 1.1]` | Reject chunk, log error with dtype and range details |
| **Disk guard** | Disk free <15% on `aziza-worker-01` | Block new model pulls, alert |

---

## Verification Plan

### Automated Tests
```bash
pytest tests/test_ollama_health.py -v               # Ollama availability, model load
pytest tests/test_audio_pipeline.py -v --tb=short    # normalization, screech
pytest tests/test_session_isolation.py -v            # concurrent sessions, no state leak
```

### Manual Verification
- Mic test against voice-to-voice endpoint → confirm `mean_abs` > 0.001 in logs (not silence-looping).
- Text-to-text round trip via Ollama → confirm response returns within target latency.
- Restart `aziza-worker-01` services → confirm Ollama and gateway come back under supervision without
  manual intervention.
- `df -h` check → confirm disk headroom before declaring phase complete.

---

## Exit Criteria
- [ ] Ollama supervised and passes health check after a simulated crash/restart
- [ ] Deploy pipeline confirmed to update the running service (not just the filesystem)
- [ ] Nginx routes gateway/ASR/voice endpoints
- [ ] Voice-to-voice mic test produces clean, non-silent audio
- [ ] No ghost sessions after a client hard-disconnect (GPU slot released)
- [ ] Orchestrator survives a session-state write/read cycle without crash-looping
- [ ] Disk free >20% on `aziza-worker-01`
