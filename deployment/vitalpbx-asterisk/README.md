# deploy/vitalpbx-asterisk

**Status:** VitalPBX 4.5.x + Asterisk 20.18.2 are **live on VM-B**. `TRUNK_01` is **live and validated** (Phase 2 Stage 1 closed 2026-05-15). The live endpoint — including the Phase A audio-quality settings — is captured as a source-of-truth snapshot in [`pjsip_TRUNK_01.reference.conf`](pjsip_TRUNK_01.reference.conf). **Phase A durability: RESOLVED 2026-05-16** — the Phase A settings are now DB-backed via a dedicated VitalPBX Device Profile (`CARRIER-TRUNK` → Asterisk template `[p13]`, trunk bound as `[TRUNK_01](p13)`); they survive UI "Apply Changes"/regeneration. Verified live after a real regeneration cycle, with no carrier-facing signaling regression (procedure + evidence in that reference file). Phase 3 dialplan + ARI user **slice 1 in repo** (`extensions_amd.conf`, `ari_amd.conf`, `include_extensions_custom.snippet`).

Configuration snippets for the PBX/media engine on VM-B `core-server-telephony` (`46.224.207.237` / `10.9.0.3`). We do **not** fork VitalPBX or Asterisk source — only the configs and dialplan we author.

> **SSH access** — `ssh sida-pbx` for VM-B (this PBX). See [Docs/REFERENCE_Hosts_and_SSH_Aliases.md](../../Docs/REFERENCE_Hosts_and_SSH_Aliases.md) for the canonical host list.

What belongs here:

- `extensions_custom.conf` dialplan snippets (inbound `from-trunk`, parallel-greeting + AMD branch, queue/ACD entry, AI lane, escalation lane).
- PJSIP trunk template for SkyTel (host, port, transport, codec list, DTMF, NAT).
- AMI user definition consumed by [tools/ami-originate/](../../tools/ami-originate/) and [services/dialer-worker/](../../services/dialer-worker/).
- ARI Stasis app config consumed by [services/adapter/](../../services/adapter/).
- MixMonitor stereo-recording config (left = subscriber, right = AI/operator).
- Webhook config that POSTs to [Qube_Web/.../api/integrations/asterisk/webhook](../../Qube_Web/src/app/api/integrations/asterisk).

References:

- Setup walkthrough: [Docs/claude_review/Setup_Guide_2_PBX.md](../../Docs/claude_review/Setup_Guide_2_PBX.md).
- Stage-1 PBX runbook: [Docs/phase2/06_GUIDE_Stage_1_PBX_Setup.md](../../Docs/phase2/06_GUIDE_Stage_1_PBX_Setup.md).
- Expected call flow with port detail: [Docs/phase2/08_REFERENCE_Call_Flow_Architecture.md](../../Docs/phase2/08_REFERENCE_Call_Flow_Architecture.md).
- Firewall matrix: [Docs/phase5/Phase_5_VM_B_Port_Service_and_Firewall_Matrix.md](../../Docs/phase5/Phase_5_VM_B_Port_Service_and_Firewall_Matrix.md).
