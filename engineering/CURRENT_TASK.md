# Current Task

**Task**: Security Blockers Phase 1 — Hardening, Monitoring, Resilience, Testing
**Branch**: `security/blockers-phase1`
**Status**: IN PROGRESS (Epics 1-3 committed, Epic 4 active)

## Summary

Comprehensive security hardening and production readiness work across all services. Builds on PI-1 (10 Epics complete) and PI-4 (Uzbek adapter trained and deployed). Addresses findings from security audits and operational gaps identified in PI-1 certification.

## Completed Epics

| Epic | Status | Commit | Description |
|------|--------|--------|-------------|
| Epic 1 | DONE | `3d99c10` | Security Blockers Phase 1 — 218 files (auth, monitoring, resilience, LiveKit, testing, deployment) |
| Epic 2 | DONE | `47ac6c9` | Production TLS & Reverse Proxy — Nginx + self-signed certs + security headers |
| Epic 3 | DONE | `36f1497` | API Key Management & Rate Limiting — API keys module + named throttlers |
| Epic 4 | ACTIVE | — | CI/CD Pipeline Completion |

## Epic 4: CI/CD Pipeline Completion

Current `.github/workflows/ci.yml` only tests the API Gateway. Expanding to:

- **Frontend**: npm ci + build + test
- **Python**: pytest for orchestrator, moshi-worker, persona-plex
- **Lint**: ESLint + Prettier checks
- **Security**: npm audit + Python safety checks
- **Build verification**: TypeScript compilation + frontend build

## Service Ports

| Port | Service |
|------|---------|
| 8080 | API Gateway (NestJS) |
| 8001 | Orchestrator |
| 8000 | PersonaPlex (FastAPI) |
| 8002 | vLLM English |
| 8003 | vLLM Uzbek |
| 5173 | Frontend (Vite dev) |

## Governance

- Architecture Freeze: Enforced (no new frameworks, databases, or languages)
- Services: vllm-english STOPPED, vllm-uzbek ERRORED (pre-existing)
- Active branch: `security/blockers-phase1`
