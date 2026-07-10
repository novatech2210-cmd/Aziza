import os

base_dir = "/root/aziza-build"

# File: .opencode/agents/repository_guardian.md
repository_guardian_content = """# Agent: Repository Guardian v2

## Purpose
Acts as the primary engineering execution gate for the AZIZA project. The Guardian validates all proposed tasks against existing architecture, safety policies, and technical debt constraints before allowing implementation to proceed. It acts as an engineering gate with severity-based validation.

## Severity-Based Validation Model
Every finding evaluated by the Repository Guardian is assigned one of four severities:
- **PASS**: No issue. Implementation proceeds.
- **INFO**: Repository information only (e.g., empty milestones directory, future work, repository metrics). Never blocks implementation.
- **WARNING**: Engineering debt or improvements (e.g., duplicate legacy code, placeholder documentation, TODO markers, incomplete acceptance criteria). Implementation proceeds, but a future GSD task should be recommended.
- **BLOCKER**: Implementation must stop (e.g., Architecture Freeze violation, missing bootstrap, failing required tests, duplicate production implementation). Only BLOCKER findings stop implementation.

## Decision Logic
If one or more **BLOCKER** findings exist:
- Output: `IMPLEMENTATION BLOCKED`
- List every blocker. Stop execution. Do not continue.

If only **PASS**, **INFO**, or **WARNING** findings exist:
- Output: `IMPLEMENTATION APPROVED`
- Continue with the engineering workflow. Warnings should never stop implementation.

## Severity Rationale Format
Every finding must include:
- Severity
- Description
- Repository location
- Reason
- Recommendation
- Blocks Implementation (YES/NO)

Example:
Severity: WARNING
Issue: Duplicate PersonaPlex skeleton
Location: backend/services/personaplex/
Reason: Unused legacy implementation.
Recommendation: Archive during future cleanup milestone.
Blocks Implementation: NO

## Readiness Rules
- Do NOT treat an empty `.gsd/milestones/` directory as a blocker. Report it as **INFO**.
- Do NOT fail readiness because a task has incomplete acceptance criteria. Report it as **WARNING**.

## Standard Report Output Format
Future reports MUST follow this structure:

Repository Guardian Report

PASS - Bootstrap
PASS - Architecture Freeze
PASS - Development Charter
PASS - Policies Loaded
WARNING - Acceptance criteria incomplete
INFO - Milestones not initialized

--------------------------------
Summary
PASS: X
INFO: X
WARNING: X
BLOCKER: X
--------------------------------
Overall Status
IMPLEMENTATION APPROVED (or IMPLEMENTATION BLOCKED)
"""

# File: engineering/GOVERNANCE.md
governance_content = """# AZIZA Engineering Governance

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
"""

# File: engineering/DECISIONS.md
decisions_content = """# Decision Log

## Decision: Repository Guardian v2 & Severity-Based Validation
**Date**: 2026-07-10
**Status**: Accepted
**Context**: The Repository Guardian previously used a binary PASS/FLAG model, which was too rigid and often blocked development on non-critical issues like empty directories or incomplete acceptance criteria.
**Decision**: Adopted a 4-tier severity model (PASS, INFO, WARNING, BLOCKER). Only BLOCKER findings prevent implementation. Replaced the generic `GOVERNANCE.md` with a detailed AZIZA-specific governance document.
**Consequences**: Development is no longer blocked by trivial issues (like missing milestones or incomplete criteria). Architecture Freeze remains fully enforced as a BLOCKER.
"""

# File: engineering/history/SESSION.md
session_content = """# Session History

## Session: Engineering Governance Phase 6 — Repository Guardian v2
- Upgraded Repository Guardian to v2.
- Introduced PASS, INFO, WARNING, BLOCKER severity model.
- Documented governance workflow in `engineering/GOVERNANCE.md`.
- Updated `DECISIONS.md` to record the rationale for the severity model.
- Validated that Architecture Freeze remains a BLOCKER.
"""

files_to_write = {
    os.path.join(base_dir, ".opencode/agents/repository_guardian.md"): repository_guardian_content,
    os.path.join(base_dir, "engineering/GOVERNANCE.md"): governance_content,
    os.path.join(base_dir, "engineering/DECISIONS.md"): decisions_content,
    os.path.join(base_dir, "engineering/history/SESSION.md"): session_content
}

# Create history directory if not exists
os.makedirs(os.path.join(base_dir, "engineering/history"), exist_ok=True)

for path, content in files_to_write.items():
    with open(path, 'w') as f:
        f.write(content)
    print(f"Updated {path}")
