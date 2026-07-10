# `deploy/kamailio/` — Kamailio config (local-first IaC)

Local mirror of the Kamailio configuration on **VM-A `sida-kam`** (`kamailio-edge`, public `178.104.152.17` / private `10.9.0.2`). Edit files in this folder with full VS Code experience, then `push.ps1` ships them to the VM, validates, applies atomically, reloads, and tails the journal.

Kamailio is a SIP proxy — signalling only, no audio. It accepts INVITEs from the carrier (today: Nano Telecom — `TRUNK_01`, server `146.120.19.68`) and relays them over the private network to VitalPBX/Asterisk on VM-B. See [Docs/claude_review/Setup_Guide_1_Kamailio.md](../../Docs/claude_review/Setup_Guide_1_Kamailio.md) for the architecture and the §6–§8 configuration walkthrough.

---

## Files in this folder

| File | Source on VM-A | Status | Purpose |
| --- | --- | --- | --- |
| `kamailio.cfg` | `/etc/kamailio/kamailio.cfg` | **Edit this.** Pulled 2026-05-07 from VM-A. | Main Kamailio configuration. The file `push.ps1` ships. |
| `kamctlrc` | `/etc/kamailio/kamctlrc` | Reference only. Pulled 2026-05-07. | DB credentials for the `kamctl` CLI tool. Rarely changed. |
| `etc-default-kamailio` | `/etc/default/kamailio` | Reference only. Pulled 2026-05-07. | Debian service defaults (mostly commented). Used by the init script, not by systemd directly. |
| `push.ps1` | — | Tooling. | Push + validate + atomic apply + reload + tail. See workflow below. |
| `README.md` | — | This file. | Layout, workflow, rollback. |

The hash check on initial pull was clean: `kamailio.cfg` SHA256 matches what's on VM-A.

---

## Workflow

```powershell
# 1. Edit kamailio.cfg in this folder (VS Code, full UX, this same window).

# 2. Preview the diff against live without pushing
.\push.ps1 -DryRun
# or .\push.ps1 -Diff (same thing)

# 3. Push for real — stages, validates, backs up, applies, reloads, tails
.\push.ps1

# Re-sync the local file from VM-A (if anyone edited /etc/kamailio/ directly)
.\push.ps1 -Pull
```

`push.ps1` semantics, in order:

1. **scp** local file → `${RemoteHost}:/etc/kamailio/kamailio.cfg.new.<UTC-timestamp>`.
2. **Validate** on remote: `kamailio -c -f /etc/kamailio/kamailio.cfg.new.<ts>`. If validation fails, the staged file is removed and **the live config is NOT touched**.
3. **Backup** the current live file to `/etc/kamailio/kamailio.cfg.bak.<UTC-timestamp>`.
4. **Atomic apply** — `mv` from the staged path to `/etc/kamailio/kamailio.cfg`. Same filesystem, so the rename is atomic; in-flight calls are not affected.
5. **Reload** — `systemctl reload kamailio` (graceful; falls back to `restart` only if reload fails).
6. **Verify** — `systemctl is-active kamailio` must return `active`. If not, the script exits with a rollback hint.
7. **Tail** — last 15 lines of `journalctl -u kamailio` so you see immediate fallout.

The push aborts at step 2 (validation) for any syntax error. Live config is never touched on a bad push.

---

## Rollback

Every push leaves a timestamped backup on VM-A. To roll back:

```powershell
# List backups
ssh sida-kam "ls -la /etc/kamailio/kamailio.cfg.bak.*"

# Restore a specific backup and reload
ssh sida-kam "cp /etc/kamailio/kamailio.cfg.bak.<timestamp> /etc/kamailio/kamailio.cfg && systemctl reload kamailio"
```

Then `.\push.ps1 -Pull` to refresh the local mirror to match.

For a "rollback right now" scenario `push.ps1` already prints the exact command in its closing notes, so you don't have to look it up.

---

## What belongs in this folder long-term

- `kamailio.cfg` — primary config (this is the authority once we start version-controlling).
- ACL / IP-allowlist for **carrier SBC CIDRs** (currently `146.120.19.0/24` for Nano Telecom; tighten when Nano names exact /32s — see [`Docs/phase2/07_FORM_Stage_1_Carrier_Input_Sheet.md` §H item 2](../../Docs/phase2/07_FORM_Stage_1_Carrier_Input_Sheet.md)).
- Multi-domain / multi-tenant SIP routing tables (`X-Tenant-ID` header or domain-based) — Stage 2+.
- TLS material **layout** for optional 5061 (cert paths, not certs) — when/if we enable TLS.
- systemd override snippets — none today; add here if any are introduced.

What does **not** belong here:

- Private TLS keys / certs (separate secret-management workflow).
- `kamctlrc` DB credentials in the form actually used at runtime (the file here is for reference; the live one on VM-A holds the real values).
- Anything carrier-secret (SIP passwords). Trunk credentials live on the PBX side ([07_FORM Carrier Input Sheet](../../Docs/phase2/07_FORM_Stage_1_Carrier_Input_Sheet.md)) — Kamailio does not handle them.

---

## Source-of-truth contract

After `push.ps1` runs, VM-A's live file and the local file in this folder are in sync. The convention going forward:

| Scenario | What to do |
| --- | --- |
| Normal edit | Edit `kamailio.cfg` locally → `push.ps1`. |
| Suspect drift (someone edited the VM directly) | `push.ps1 -Pull` first, then resume normal edits. |
| Emergency edit on the VM (3 a.m. fix) | OK — but `push.ps1 -Pull` afterwards to bring the change back here, otherwise the next normal push will overwrite it. |
| New carrier / Stage-2 routing | Edit locally, `push.ps1 -DryRun` to preview, then `push.ps1`. Validation is your friend. |

---

## References

- [Setup_Guide_1_Kamailio.md](../../Docs/claude_review/Setup_Guide_1_Kamailio.md) — config walk-through (§6) and the live-trunk wiring steps (§8).
- [07_FORM_Stage_1_Carrier_Input_Sheet.md §E](../../Docs/phase2/07_FORM_Stage_1_Carrier_Input_Sheet.md) — carrier SBC CIDR for the source-allowlist.
- [10_REFERENCE_Trunk_Carrier_Identity_Check.md](../../Docs/phase2/10_REFERENCE_Trunk_Carrier_Identity_Check.md) — why `TRUNK_01` is Nano Telecom.
- [Phase_1_Real_Server_Construction_Guide.md §4](../../Docs/phase1/Phase_1_Real_Server_Construction_Guide.md) — VM-A as-built.
- [Recommended_Stack_and_Project_Structure.md §4](../../Docs/2026-04-08/Recommended_Stack_and_Project_Structure.md) — multi-tenant model context.
