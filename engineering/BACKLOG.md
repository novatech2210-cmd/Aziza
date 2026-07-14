# Engineering Backlog

## Critical
- ~~Monitor VRAM utilization across 3 concurrent vLLM instances.~~ **IMPLEMENTED** (gpu-metrics.service.ts)
- ~~Implement real GPU metrics for admin dashboard (currently mocked).~~ **IMPLEMENTED** (gpu-metrics.service.ts + GpuDashboard.vue)
- ~~Commit and push security blockers phase 1.~~ **DONE** (commit `3d99c10`, pushed)

## High
- ~~Fully integrate the newly trained Uzbek and Russian adapters into production paths cleanly.~~ **IMPLEMENTED** (moshi_uz_v1 deployed, moshi_ru_v1 loaded)
- ~~Fix broken test coverage in the frontend suite.~~ **IMPLEMENTED** (auth.test.js, chat.test.js, uuid.test.js)
- ~~Add error aggregation from all services to MongoDB.~~ **IMPLEMENTED** (error-aggregation.service.ts)
- ~~Add health check endpoints for all services.~~ **IMPLEMENTED** (health-check.service.ts)
- ~~Verify monitoring module integrates with app.module.ts.~~ **VERIFIED** (imported in app.module.ts)
- ~~Verify auth guards are wired into route definitions.~~ **VERIFIED** (@UseGuards on admin controller)
- **NEW**: Verify structured logging modules are imported by Python services
- ~~Run full test suite after staging.~~ **DONE** (72 NestJS PASS, 13 frontend PASS, 6/7 Python PASS)
- ~~Centralize log aggregation from all services.~~ **DONE** (Epic 5, LogCollectorService + LogViewer.vue)

## Medium
- ~~Set up automated CI/CD for the repository.~~ **DONE** (.github/workflows/ci.yml)
- Migrate `mcp/` logic into the standard backend architecture if still needed.
- ~~Add emotion detection to PersonaPlex.~~ **COMPLETED** (26/26 tests pass, PI-4)
- Implement context window management for long conversations.
- ~~Wire rate limiting into NestJS gateway.~~ **DONE** (Named throttlers: global/auth/api + Nginx edge)
- ~~Add Nginx reverse proxy with TLS/HTTPS.~~ **DONE** (Epic 2, commit `47ac6c9`)
- ~~Add API key management for external consumers.~~ **DONE** (Epic 3, commit `36f1497`)
- ~~Centralized log aggregation.~~ **DONE** (Epic 5, LogCollectorService + admin API + LogViewer.vue)
- **NEW**: Run 30-min and 60-min stress tests (10-min passed)
- **NEW**: Complete WER/CER measurement (script ready, needs audio recordings)
- **NEW**: Obtain valid TLS certificates for production (self-signed for dev only)

## Low
- Clean up unused dependencies in `package.json`.
- Add PWA manifest for mobile installability.
- Add i18n for UI strings (RU, UZ, EN).
- ~~Remove deprecated deployment scripts.~~ **DONE** (get_vast.py, get_vast_ssh.py deleted)
- **NEW**: Complete barge-in / interruption handling test
- **NEW**: Run LiveKit room voice conversation test

## Future Improvements
- Multi-node inference scaling.
- Multi-worker V2V scaling.
- Session isolation at GPU level.
- Centralized log aggregation (structured logging modules exist, need aggregator layer like Loki/ELK)
