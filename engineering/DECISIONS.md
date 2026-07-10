# Decision Log

## Decision: Repository Guardian v2 & Severity-Based Validation
**Date**: 2026-07-10
**Status**: Accepted
**Context**: The Repository Guardian previously used a binary PASS/FLAG model, which was too rigid and often blocked development on non-critical issues like empty directories or incomplete acceptance criteria.
**Decision**: Adopted a 4-tier severity model (PASS, INFO, WARNING, BLOCKER). Only BLOCKER findings prevent implementation. Replaced the generic `GOVERNANCE.md` with a detailed AZIZA-specific governance document.
**Consequences**: Development is no longer blocked by trivial issues (like missing milestones or incomplete criteria). Architecture Freeze remains fully enforced as a BLOCKER.
