# Decision Log

## Decision: Repository Guardian v2 & Severity-Based Validation
**Date**: 2026-07-10
**Status**: Accepted
**Context**: The Repository Guardian previously used a binary PASS/FLAG model, which was too rigid and often blocked development on non-critical issues like empty directories or incomplete acceptance criteria.
**Decision**: Adopted a 4-tier severity model (PASS, INFO, WARNING, BLOCKER). Only BLOCKER findings prevent implementation. Replaced the generic `GOVERNANCE.md` with a detailed AZIZA-specific governance document.
**Consequences**: Development is no longer blocked by trivial issues (like missing milestones or incomplete criteria). Architecture Freeze remains fully enforced as a BLOCKER.

## Decision: In-Process Alerting Over External Stack
**Date**: 2026-07-11
**Status**: Accepted
**Context**: Epic 9 requires alerting and anomaly detection. External monitoring stacks (Grafana, Prometheus, Sentry) add infrastructure complexity and violate the Architecture Freeze.
**Decision**: Implement in-process rule-based alerting within the NestJS gateway. Rules evaluate every 30 seconds against MetricsService and GPU metrics. Alerts persist to MongoDB via ErrorAggregationService. Cooldowns prevent alert storms.
**Consequences**: No external dependencies added. Alerting is limited to metrics available within the gateway process. External monitoring can be added later without code changes (correlation IDs enable distributed tracing).

## Decision: Structured Logging via Custom Module Over OpenTelemetry
**Date**: 2026-07-11
**Status**: Accepted → **Implemented** (security blockers phase 1)
**Context**: OpenTelemetry is installed in the venv but unused. Full OTEL integration requires SDK initialization, exporter configuration, and collector setup — significant complexity for PI-1.
**Decision**: Implement structured JSON logging with correlation IDs using a custom module. Each Python service (moshi-worker, orchestrator, persona-plex) gets a `structured_logging.py` module. NestJS uses a CorrelationIdMiddleware. Logs persist to MongoDB capped collections.
**Consequences**: Correlation IDs propagate within each service. Cross-service trace correlation requires log correlation by sessionId or timestamp. Full OpenTelemetry can be layered on top later.
**Implementation**: `structured_logging.py` exists in moshi-worker, orchestrator, and persona-plex. `correlation-id.middleware.ts` exists in api-gateway middleware. All files untracked (not yet committed).

## Decision: Native Moshi LoRA Over PEFT Adapter
**Date**: 2026-07-13
**Status**: Accepted → **Implemented** (PI-4)
**Context**: PEFT's `peft.tuners.lora.layer.Linear` caused crashes when loaded into Moshi's custom model architecture. The base model uses native `LoRALinear` layers, not standard PyTorch linear layers.
**Decision**: Train adapters using Moshi's native LoRA implementation (`LoRALinear`), bypassing PEFT entirely. Adapter weights saved as `safetensors` with custom loading logic in `moshi_engine.py`.
**Consequences**: Adapter loading is stable (no PEFT dependency). Training scripts (`train_moshi_lora.py`) use custom Moshi-aware training loop. Future adapter work must follow the native Moshi pattern, not PEFT conventions.

## Decision: Audio Keep-Alive Over WebSocket Pings
**Date**: 2026-07-13
**Status**: Accepted → **Implemented** (PI-4 stress testing)
**Context**: The moshi-worker closes connections with no data for 45s (stale connection protection). WebSocket ping/pong frames do not count as "data" for the worker's keep-alive check. Stress test stability was compromised by premature disconnects.
**Decision**: Send 100ms silence audio chunks every 5 seconds as application-level keep-alive, replacing WebSocket pings.
**Consequences**: Connections stay alive during idle periods. Adds ~1.6KB/s of silence traffic per connection. No impact on audio quality (silence chunks are distinguishable from speech).

## Decision: LiveKit for Production Voice Pipeline
**Date**: 2026-07-13
**Status**: Accepted → **Implemented** (PI-4 Phase 8)
**Context**: Direct WebSocket voice streaming works but lacks room management, participant tracking, and SFU capabilities needed for multi-user scenarios.
**Decision**: Integrate LiveKit as the voice infrastructure layer. LiveKit bot runs under PM2, connects to moshi-worker for inference, and bridges audio tracks.
**Consequences**: Adds LiveKit server dependency for production voice. Bot entrypoint (`livekit_bot.py`) manages room lifecycle. Capacity monitoring tracks worker availability. Architecture verified but full room-based voice conversation requires LiveKit server deployment.

## Decision: RBAC Guards for Admin Endpoints
**Date**: 2026-07-11
**Status**: Accepted → **Implemented** (security blockers phase 1)
**Context**: Admin endpoints had no role-based access control. Any authenticated user could access admin functionality.
**Decision**: Add `@Roles('admin')` decorator + `RolesGuard` guard to admin routes. JWT token carries `role` claim. Guard validates role against route requirements.
**Consequences**: Admin endpoints require `role=admin` in JWT. Frontend admin UI must request and store role in auth flow. Breaking change for existing admin users (must re-authenticate with role-bearing tokens).

## Decision: Nginx Reverse Proxy with TLS Termination
**Date**: 2026-07-14
**Status**: Accepted → **Implemented** (Epic 2)
**Context**: All traffic was plaintext HTTP. No TLS/HTTPS. No security headers at the edge. No rate limiting at the gateway level.
**Decision**: Deploy Nginx as a reverse proxy in front of the API Gateway. TLS termination on port 443 (TLSv1.2/1.3). HTTP→HTTPS redirect. Security headers added at the Nginx layer (HSTS, CSP, X-Frame-Options, etc.). Rate limiting: 60 req/min general API, 10 req/min auth endpoints. WebSocket upgrade support for /api/chat and /api/v2v. Internal network restriction for Orchestrator and PersonaPlex.
**Consequences**: All external traffic encrypted. Security headers enforced before reaching NestJS. Rate limiting reduces abuse surface. Nginx becomes a required dependency for production deployment. Self-signed certificates used for development; production must use valid certificates (Let's Encrypt or commercial).
**Implementation**: `configs/docker/infrastructure/nginx/nginx.conf`, `configs/docker/docker-compose.yml`, `backend/services/api-gateway/src/main.ts` (trust proxy + CORS update).

## Decision: API Key Management for External Consumers
**Date**: 2026-07-14
**Status**: Accepted → **Implemented** (Epic 3)
**Context**: No mechanism for external consumers to authenticate. JWT tokens are session-based and require user accounts. Need a persistent, revocable credential for programmatic API access.
**Decision**: Implement API key system with SHA-256 hashed keys (prefix `aziza_`). Keys stored in MongoDB with tier (free/pro/enterprise), scopes, expiry, and usage tracking. `@RequiresApiKey()` decorator for opt-in endpoint protection. `ApiKeyGuard` validates `X-Api-Key` header against stored hashes.
**Consequences**: External consumers can authenticate via API keys. Keys are one-way hashed (never stored plaintext). Tier system enables usage-based access control. Keys can be revoked instantly. Requires MongoDB collection for key storage.
**Implementation**: `backend/services/api-gateway/src/api-keys/` (8 files, 7 unit tests).

## Decision: Named Throttler Tiers for Rate Limiting
**Date**: 2026-07-14
**Status**: Accepted → **Implemented** (Epic 3)
**Context**: Global rate limit of 100 req/min was too coarse. Auth endpoints need stricter limits (5/min login, 3/min register). Chat endpoints need separate limits (20/min stream, 10/min voice). Single throttle configuration couldn't differentiate.
**Decision**: Configure three named throttler tiers: `global` (100 req/min), `auth` (5 req/min), `api` (60 req/min). Auth controller uses `@Throttle({ auth: ... })`. Chat controller uses `@Throttle({ api: ... })`. Nginx provides first layer of rate limiting at the edge; NestJS ThrottlerModule provides application-level enforcement.
**Consequences**: Two-layer rate limiting (Nginx + NestJS). Auth endpoints protected against brute force. Chat endpoints protected against abuse. Named tiers allow per-endpoint tuning without global config changes.

## Decision: Multi-Service CI Pipeline
**Date**: 2026-07-14
**Status**: Accepted → **Implemented** (Epic 4)
**Context**: `.github/workflows/ci.yml` only tested the API Gateway. No automated testing for frontend or Python services. No security audit steps. No build verification gate.
**Decision**: Expand CI to 4 parallel jobs: API Gateway (NestJS), Frontend (Vue 3), Python Services (matrix: orchestrator/moshi-worker/persona-plex), and Build Verification gate. Each job includes install, test, and audit steps. Python services use `continue-on-error` since they lack full test coverage. Build Verification gates on both API Gateway and Frontend passing.
**Consequences**: All three service tiers tested on every push/PR. Security audits surface known vulnerabilities. Build verification prevents broken artifacts from merging. Python tests continue-on-error until full coverage achieved.
