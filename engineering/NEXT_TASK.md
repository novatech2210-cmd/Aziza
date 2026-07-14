# Next Task

**Task**: Security Blockers Phase 1 — Hardening, Monitoring, Resilience, Testing
**Status**: Epics 1-4 COMPLETE (Epic 5 candidates below)

## Branch State

```
security/blockers-phase1 — up to date with origin
Working tree: clean
22 commits total
```

## Completed Epics

| Epic | Commit | Description |
|------|--------|-------------|
| Epic 1 | `3d99c10` | Security Blockers Phase 1 — 218 files (auth, monitoring, resilience, LiveKit, testing, deployment) |
| Epic 2 | `47ac6c9` | Production TLS & Reverse Proxy — Nginx + self-signed certs + security headers |
| Epic 3 | `36f1497` | API Key Management & Rate Limiting — API keys module + named throttlers |
| Epic 4 | `67351a3` | CI/CD Pipeline Completion — frontend, Python, lint, security audit, build verification |

## PI-2 Candidates (Prioritized)

| Priority | Item | Rationale |
|----------|------|-----------|
| P1 | Multi-GPU inference support | Single GPU bottleneck for scaling |
| P1 | Centralized log aggregation | Structured logging modules exist; need aggregator layer |
| P2 | WebSocket load/soak testing | 10-min stress test passed; 30/60-min not run |
| P2 | Transliteration-aware language detection | Detection gaps for mixed-script text |
| P3 | PWA manifest for mobile installability | Frontend is SPA, no offline support |

## Remaining PI-4 Gaps

- WER/CER measurement: Script created (`uzbek_wer_evaluation.py`), needs recorded audio
- Barge-in / interruption handling: Needs dedicated test
- 30-min and 60-min stress tests: 10-min passed, longer tests not executed
- LiveKit room voice conversation: Architecture verified, needs LiveKit server test
