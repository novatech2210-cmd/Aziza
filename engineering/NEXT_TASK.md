# Next Task

**Task**: Security Blockers Phase 1 — Commit & Validate
**Status**: IN PROGRESS (implementation done, needs staging/commit/push)

## Current State

- Branch `security/blockers-phase1` has 13 unpushed commits
- 51 modified files + 70+ untracked files exist in working tree
- Implementation spans auth hardening, monitoring module, structured logging, resilience, LiveKit, testing, deployment automation

## Immediate Next Steps (This Branch)

1. Stage all security blockers phase 1 files
2. Commit with appropriate scope (may need 2-3 commits by domain)
3. Push to origin
4. Run full test suite (50 NestJS + 7 Python + 13 frontend = 70 automated)
5. Verify service startup with new modules
6. Merge to main after CI passes

## After Security Blockers Phase 1

### PI-2 Candidates (Prioritized)

| Priority | Item | Rationale |
|----------|------|-----------|
| P0 | Nginx + TLS/HTTPS + security headers | Production traffic requires encryption |
| P0 | Rate limiting and API key management | Auth guards exist but no rate limits wired |
| P1 | Multi-GPU inference support | Single GPU bottleneck for scaling |
| P1 | CI/CD pipeline with automated testing | `.github/workflows/` scaffolded but empty |
| P2 | Centralized log aggregation | Structured logging modules exist; need aggregation layer |
| P2 | WebSocket load/soak testing | 10-min stress test passed; 30/60-min not run |
| P3 | Transliteration-aware language detection | Detection gaps for mixed-script text |

### Remaining PI-4 Gaps

- WER/CER measurement: Script created (`uzbek_wer_evaluation.py`), needs recorded audio
- Barge-in / interruption handling: Needs dedicated test
- 30-min and 60-min stress tests: 10-min passed, longer tests not executed
- LiveKit room voice conversation: Architecture verified, needs LiveKit server test

### Known Gaps (Unchanged)

1. **Security**: No TLS/HTTPS, no rate limiting at gateway level (guards exist, limits not enforced)
2. **Scalability**: Single GPU, no horizontal scaling, no load balancer
3. **Observability**: No centralized log aggregation (structured logging modules exist but no aggregator)
4. **CI/CD**: `.github/workflows/` directory exists, no workflow files
5. **Language**: Transliterated text detection gaps
6. **Persona**: CRUD duplicate key error (reported in PI-1 certification)
