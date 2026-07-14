# Current Task

**Task**: Security Blockers Phase 1 — Hardening, Monitoring, Resilience, Testing
**Branch**: `security/blockers-phase1`
**Status**: IN PROGRESS (13 commits ahead of origin, 51 modified + 70 untracked files unstaged)

## Summary

Comprehensive security hardening and production readiness work across all services. Builds on PI-1 (10 Epics complete) and PI-4 (Uzbek adapter trained and deployed). Addresses findings from security audits and operational gaps identified in PI-1 certification.

## Implementation Status (Unstaged — Exists in Working Tree)

### Auth & Security Hardening
- **Auth DTOs**: `create-user.dto.ts`, `login-user.dto.ts` (validated input schemas)
- **Roles guard**: `roles.guard.ts` (RBAC enforcement)
- **User schema**: `user.schema.ts` (typed user model)
- **Auth service expansion**: +106 lines (login hardening, validation)
- **Admin controller refactor**: +255 lines (admin API expansion)

### Monitoring Module (New)
- `monitoring.module.ts` — NestJS module integrating all monitoring services
- `alerting.service.ts` — In-process rule-based alerting with cooldowns
- `cost-tracking.service.ts` — API cost tracking per user/session
- `gpu-metrics.service.ts` — GPU utilization and VRAM monitoring
- `health-check.service.ts` — Service health endpoint aggregation
- `metrics.service.ts` — Request/latency/error metrics
- `sla-monitoring.service.ts` — SLA compliance tracking
- `structured-logging.service.ts` — Correlation ID propagation, JSON logging
- **Specs**: alerting, cost-tracking, gpu-metrics, metrics, sla-monitoring (5 spec files)

### Structured Logging (Python)
- `backend/services/moshi-worker/structured_logging.py`
- `backend/services/orchestrator/structured_logging.py`
- `backend/persona-plex/structured_logging.py`

### Resilience & Error Handling
- `all-exceptions.filter.ts` — Global NestJS exception filter
- All exception filter spec file
- Expanded error handling in moshi-worker (engine +359 lines, service +121 lines, VAD +109 lines, GPU scheduler +60 lines, LLM routing +50 lines)

### LiveKit Integration
- `livekit.controller.ts` — LiveKit API endpoints (room creation, tokens)
- `livekit-bot/livekit_bot.py` — PM2-managed LiveKit bot process
- `useLiveKitVoiceChat.js` — Frontend LiveKit voice composable

### Voice Gateway Expansion
- `voice.gateway.ts` — +214 lines (audio keep-alive, language switching)

### Frontend Improvements
- `RequestMetrics.vue`, `ServiceHealth.vue` — Admin dashboard components
- Auth store expansion (+54 lines)
- VoicePanel simplification (-72 lines, cleaner API)

### Testing Infrastructure
- **NestJS e2e tests**: `admin.e2e-spec.ts`, `auth.e2e-spec.ts`, `chat.e2e-spec.ts` + helpers
- **NestJS unit tests**: auth.service.spec.ts, alerting.spec, cost-tracking.spec, gpu-metrics.spec, metrics.spec, sla-monitoring.spec, all-exceptions.filter.spec, app.controller.spec, app.service.spec
- **Python tests**: `test_gpu_scheduler.py`, `test_vad.py`, `test_state_machine.py`, `run_tests.sh`
- **Frontend tests**: `auth.test.js`, `chat.test.js`, `uuid.test.js`
- **Load tests**: `backend/tests/load/load_test.py`, `quick_check.py`
- **Jest config**: `jest.config.js`, `tsconfig.test.json`

### Deployment Automation
- `deployment/rollback.sh` — Rollback script
- `deployment/start_services.sh` — Service startup script
- `deployment/validate_env.py` — Environment validation
- `deployment/cleanup_logs.py` — Log rotation/cleanup
- Deleted: `deployment/get_vast.py`, `deployment/get_vast_ssh.py` (superseded)

### Docker & Infrastructure
- `configs/docker/docker-compose.yml` — Expanded (+15 lines, infrastructure services)
- `configs/docker/infrastructure/` — New infrastructure config directory

### PM2 & Process Management
- `ecosystem.config.js` — +26 lines (LiveKit bot, new service entries)

### Training Artifacts (PI-4 — Committed)
- `training/datasets/uzbek/train.jsonl` (1.1MB), `val.jsonl` (125KB)
- `training/lora/adapters/` — 9 adapter directories including `moshi_uz_v1`
- `training/scripts/train_moshi_lora.py` — Production LoRA training script
- `training/scripts/extend_moshi_tokenizer.py` — Tokenizer extension
- `training/scripts/retrain_moshi_tokenizer.py` — Tokenizer retraining
- `training/scripts/smoke_test_moshi_uz.py` — Adapter smoke test
- `training/scripts/train_moshi_uz_lora.sh` — Training launch script

### Benchmark Telemetry
- 5 stability test JSON files in `benchmarks/telemetry/`
- `benchmarks/reports/stability.md` — Updated stability report
- `benchmarks/scripts/uzbek_wer_evaluation.py` — WER/CER evaluation script (committed)

### Engineering Documentation (PI-4 — Committed)
- `PI4_EVALUATION_PLAN.md`, `PI4_DEPLOYMENT_GUIDE.md`, `PI4_ROLLBACK_GUIDE.md`, `PI4_TRAINING_METRICS.md`
- `MOSHI_ARCHITECTURE.md`, `MOSHI_LORA_CONFIG.md`, `RUNBOOK.md`
- `UZBEK_DATASET_REPORT.md`, `UZBEK_TOKENIZER_REPORT.md`, `UZBEK_ADAPTER_ANALYSIS.md`
- `CERTIFICATION_REPORT.md`

### CI/CD (Scaffolded)
- `.github/workflows/` — Directory created (contents TBD)
- `.config/` — OpenCode configuration directory

## What Remains for This Branch

1. **Stage and commit** the 51 modified + 70 untracked files
2. **Push** the 13 unpushed commits to origin
3. **Run full test suite** after staging (50 NestJS + 7 Python + 13 frontend)
4. **Verify** monitoring module integrates with app.module.ts
5. **Verify** auth guards are wired into routes
6. **Verify** structured logging modules are imported by services
7. **Update** deployment scripts for current service topology

## PI-4 Status (Committed)

All 10 phases documented COMPLETE. Remaining measurable gaps:
- WER/CER measurement requires recorded assistant audio (script ready)
- Barge-in / interruption handling requires dedicated test
- 30-min and 60-min stress tests not yet run (10-min passed)

## Governance

- Architecture Freeze: Enforced (no new frameworks, databases, or languages)
- Services: vllm-english STOPPED, vllm-uzbek ERRORED (pre-existing)
- Active branch: `security/blockers-phase1` (13 commits ahead, 0 pushed)
