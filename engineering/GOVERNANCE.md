# AZIZA Engineering Governance

## Purpose
To define the authoritative engineering governance model for the AZIZA project, ensuring all changes adhere to strict architectural constraints and workflow requirements.

## Engineering Governance Model
AZIZA operates under a strict autonomous engineering environment governed by the **GSD (Get Shit Done)** task lifecycle and the **OpenCode** execution policies.
- **GSD**: Generates and manages the task lifecycle (Epics, Stories, Tasks).
- **OpenCode**: Executes the tasks under strict governance.
- **Repository Guardian**: The primary execution gate that validates proposed tasks against policies.
- **Development Charter**: Defines immutable rules for development.
- **Architecture Freeze**: Prevents any changes to the system architecture without explicit human approval.

## Severity Model & Implementation Approval Process
The Repository Guardian uses a 4-tier severity model:
- **PASS**: No issue.
- **INFO**: Informational (e.g., empty milestones). Does not block.
- **WARNING**: Tech debt or non-critical gaps (e.g., incomplete acceptance criteria). Does not block.
- **BLOCKER**: Critical violation (e.g., Architecture Freeze breach, missing BOOTSTRAP). Stops implementation immediately.

Implementation is **APPROVED** if there are zero BLOCKER findings. Implementation is **BLOCKED** if one or more BLOCKER findings exist.

## Documentation & Review Responsibilities
- Agents must always update engineering documentation (e.g., `PROJECT.md`, `ARCHITECTURE.md`) when making relevant changes.
- All code changes must pass the Completion Gates: Implementation, Quality, Documentation, and Review.

## Task Lifecycle & Completion Gates
1. Task defined via GSD.
2. Bootstrap Sequence followed.
3. Repository Guardian Audit (Gate).
4. Execution & Testing.
5. Review & Documentation update.
6. Commit & Close.

## Decision Recording
All significant architectural or governance changes must be recorded in `engineering/DECISIONS.md`.
