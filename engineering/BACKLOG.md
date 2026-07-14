# Engineering Backlog

## Critical
- ~~Monitor VRAM utilization across 3 concurrent vLLM instances.~~ **IMPLEMENTED** (gpu-metrics.service.ts, untracked)
- ~~Implement real GPU metrics for admin dashboard (currently mocked).~~ **IMPLEMENTED** (gpu-metrics.service.ts + GpuDashboard.vue, untracked)
- **NEW**: Commit and push security blockers phase 1 (51 modified + 70 untracked files, 13 unpushed commits)

## High
- ~~Fully integrate the newly trained Uzbek and Russian adapters into production paths cleanly.~~ **IMPLEMENTED** (moshi_uz_v1 deployed, moshi_ru_v1 loaded, untracked moshi-engine.py changes)
- ~~Fix broken test coverage in the frontend suite.~~ **IMPLEMENTED** (auth.test.js, chat.test.js, uuid.test.js added, untracked)
- ~~Add error aggregation from all services to MongoDB.~~ **IMPLEMENTED** (error-aggregation.service.ts, untracked)
- ~~Add health check endpoints for all services.~~ **IMPLEMENTED** (health-check.service.ts, untracked)
- **NEW**: Verify monitoring module integrates with app.module.ts (module exists, wiring unverified)
- **NEW**: Verify auth guards are wired into route definitions
- **NEW**: Verify structured logging modules are imported by Python services
- **NEW**: Run full test suite after staging (50 NestJS + 7 Python + 13 frontend)

## Medium
- ~~Set up automated CI/CD for the repository.~~ **SCAFFOLDED** (.github/workflows/ directory exists, no workflow files)
- Migrate `mcp/` logic into the standard backend architecture if still needed.
- ~~Add emotion detection to PersonaPlex.~~ **COMPLETED** (26/26 tests pass, PI-4)
- Implement context window management for long conversations.
- **NEW**: Wire rate limiting into NestJS gateway (auth guards exist, no limits enforced)
- **NEW**: Add Nginx reverse proxy with TLS/HTTPS
- **NEW**: Add API key management for external consumers
- **NEW**: Run 30-min and 60-min stress tests (10-min passed)
- **NEW**: Complete WER/CER measurement (script ready, needs audio recordings)

## Low
- Clean up unused dependencies in `package.json`.
- Add PWA manifest for mobile installability.
- Add i18n for UI strings (RU, UZ, EN).
- Remove deprecated `deployment/get_vast.py` and `deployment/get_vast_ssh.py` (already deleted in working tree)
- **NEW**: Complete barge-in / interruption handling test
- **NEW**: Run LiveKit room voice conversation test

## Future Improvements
- Multi-node inference scaling.
- Multi-worker V2V scaling.
- Session isolation at GPU level.
- Centralized log aggregation (structured logging modules exist, need aggregator layer like Loki/ELK)
