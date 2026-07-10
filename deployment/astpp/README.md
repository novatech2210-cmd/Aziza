# deploy/astpp

**Status:** DB + DB user **pre-created on VM-B**; ASTPP web app install **deferred**. No billing pipeline today.

Holds the integration contract and DB notes for ASTPP (Asterisk-based open-source telecom billing).

What belongs here:

- DB schema notes (existing `astpp` schema on MariaDB 10.11.14, user `astpp@localhost`).
- Account ↔ `tenant_id` mapping convention.
- Integration contract that [services/integrations/astpp-sync/](../../services/integrations/astpp-sync/) implements.
- Cutover notes for the eventual ASTPP → CGRateS migration (`RatingPort` interface).

We do **not** check in ASTPP source — it's an installed product. This folder is documentation + glue.

References:

- Approved-plan baseline: [Docs/2026-04-08/Recommended_Stack_and_Project_Structure.md §2.1](../../Docs/2026-04-08/Recommended_Stack_and_Project_Structure.md), [§8.1](../../Docs/2026-04-08/Recommended_Stack_and_Project_Structure.md).
- Phase-1 status (DB-only, app deferred): [Docs/phase1/Phase_1_Current_Status_and_Remaining_Work.md](../../Docs/phase1/Phase_1_Current_Status_and_Remaining_Work.md).
- Stage-1 classification (non-blocker): [Docs/claude_review/Project_Status_Review_2026-05-01.md §6.3](../../Docs/claude_review/Project_Status_Review_2026-05-01.md).
