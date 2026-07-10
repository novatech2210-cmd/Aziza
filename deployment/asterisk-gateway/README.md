# `deploy/asterisk-gateway/` — TAS-IX gateway IaC

| Field | Value |
| --- | --- |
| Document reference | DEPLOY-GATEWAY-001 |
| Version | 1.0 |
| Date | 2026-05-08 |
| Purpose | Source-of-truth for the office TAS-IX gateway's Asterisk config. Local-first IaC; the live VM is one `./push.ps1` away. |

The office gateway runs Asterisk 20.19.0 (built from source) on a Hyper-V Debian 12 VM hosted on Ivan's Lenovo IdeaPad in the Sida Tashkent office. It is the carrier-facing edge for `TRUNK_01` (Nano Telecom UZ).

> **SSH access** — `ssh sida-gateway` for this office gateway, `ssh sida-kam` for the upstream Kamailio. See [Docs/REFERENCE_Hosts_and_SSH_Aliases.md](../../Docs/REFERENCE_Hosts_and_SSH_Aliases.md) for the canonical host list.

## What lives here

| File | Role |
| --- | --- |
| `pjsip.conf` | PJSIP transport, endpoints, AORs, identifies, and the two registrations (`trunk_nano_reg` to Nano, `trunk_kam_reg` to Kamailio) |
| `pjsip.secrets.conf.example` | Template for `pjsip.secrets.conf` — committed |
| `pjsip.secrets.conf` | Real `[trunk_nano_auth]` block with the live Nano password — **gitignored** |
| `extensions.conf` | Cross-trunk forwarder dialplan (`from-nano` and `from-vma`) |
| `rtp.conf` | RTP UDP port range (10000-20000) |
| `push.ps1` | Local-first push: stage → backup → atomic apply → targeted Asterisk reload |
| `.gitignore` | Blocks `pjsip.secrets.conf` (real secrets) |

## Architecture role

```
   carrier (Nano UZ)                                       internal LAN
   146.120.19.68                                           10.9.0.0/24
        ▲ │                                                    ▲
        │ │ REGISTER + INVITE                                  │
        │ ▼                                                    │
   ┌────┴──┐                       ┌──────────────┐  SIP/RTP  ┌─────────┐
   │ trunk │                       │   Kamailio   │ ◀────────▶│  VM-B   │
   │ nano  │                       │    (VM-A)    │           │ Asterisk│
   └───────┘                       │ public 178.. │           │ 10.9.0.3│
        │                          │ tailnet      │           └─────────┘
        │                          │ 100.94.66.56 │
        │                          └──────────────┘
        │                                  ▲
        │              SIP over Tailscale  │
        │              (encrypted UDP/UDP-or-DERP-TCP)
        ▼                                  │
   ┌──────────┐                             │
   │ gateway  │ ─── REGISTER every 30s ────┘
   │ tailnet  │
   │ 100.126. │ (Tailscale handles NAT/keepalive)
   │  178.27  │
   └──────────┘
```

- **Inbound calls (Nano → user)**: Nano sends INVITE to gateway → `from-nano` context → Dial(PJSIP/${EXTEN}@trunk_vma) → Kamailio over the Tailscale tunnel → VM-B → extension rings.
- **Outbound calls (user → Nano)**: VM-B sends INVITE to Kamailio → Kamailio reads `$sht(gw=>addr)` (gateway's tailnet IP+port from its REGISTER) → forwards INVITE through tailscale0 → gateway `from-vma` context → Dial(PJSIP/${EXTEN}@trunk_nano) → Nano → callee.
- **The tunnel stays open** because Tailscale runs `tailscaled` as a system service that maintains its own keepalives and falls back to DERP TCP relays if direct UDP is blocked.

### Why Tailscale (and not plain SIP, or plain WireGuard)

The office 5G ISP runs **deep-packet inspection** that drops anything matching SIP wire-signatures, on any port, UDP or TCP. Discovered 2026-05-08 — see [`Docs/phase2/12_REFERENCE_Session_Log_2026-05-08.md`](../../Docs/phase2/12_REFERENCE_Session_Log_2026-05-08.md) §4 for the test data.

Direct WireGuard (UDP/51820) **established successfully but suffered ~90-100% packet loss** on the resulting persistent UDP flow. Root cause = multi-layer consumer NAT at the office (Hyper-V Default Switch → Windows host → Nokia CPE → carrier CGN); each layer has independent UDP flow tracking, and persistent fixed-source UDP flows accumulate drops.

**Tailscale solves both at once**:
- Encrypted between peers → DPI sees only random bytes → not SIP-classified
- Aggressive NAT-traversal + ephemeral-port management → reliable delivery through 3-layer NAT
- Auto-falls back to DERP TCP relays if direct UDP fails

Result: 0% packet loss in sustained ping tests; `tailscale ping` reports direct UDP path (no DERP needed).

If we migrate the gateway to a UZ-cloud VPS with a normal ISP, Tailscale still gives value (auto-handles roaming public IPs, simplifies firewall, future-proofs ops); or we can move to plain SIP-over-public-IP at that point if we want to cut Tailscale Inc. out of the path.

## How to use

### First-time setup on a fresh workstation

```powershell
# 1. Copy the secrets template and fill in the live Nano password
Copy-Item pjsip.secrets.conf.example pjsip.secrets.conf
notepad pjsip.secrets.conf   # replace REPLACE_ME with the real password

# 2. Sanity-check what would be pushed
./push.ps1 -DryRun

# 3. Push
./push.ps1
```

### Daily editing flow

```powershell
# Pull current live state into local files (in case anyone edited /etc/asterisk/ directly)
./push.ps1 -Pull

# Edit the file you care about (pjsip.conf / extensions.conf / etc.)
code pjsip.conf

# Diff vs live, then push
./push.ps1 -DryRun
./push.ps1
```

### Rollback after a bad push

`push.ps1` prints a per-file rollback command at the end. Each file gets its own timestamped backup like `/etc/asterisk/pjsip.conf.bak.20260508-153027`. To revert one file:

```bash
ssh sida-gateway "cp /etc/asterisk/pjsip.conf.bak.<timestamp> /etc/asterisk/pjsip.conf && asterisk -rx 'core reload'"
```

## Verifying after a push

```bash
ssh sida-gateway 'asterisk -rx "pjsip show registrations"'
# Expect TWO Registered entries:
#   trunk_nano_reg/sip:146.120.19.68:5060   ... Registered (exp. ~50s)
#   trunk_kam_reg/sip:100.94.66.56:5060     ... Registered (exp. ~25s)

ssh sida-gateway 'asterisk -rx "pjsip show endpoints"'
# Expect: trunk_nano (Not in use), trunk_vma (Not in use)

ssh sida-gateway 'tailscale ping 100.94.66.56'
# Expect: pong via 178.104.152.17:<port> (direct UDP path, no DERP)
```

If `trunk_kam_reg` shows `Rejected` or `Unregistered`:
1. **Check Tailscale tunnel** is up on both ends: `tailscale status` on each VM should show the other peer as online.
2. **Check Kamailio allowlist**: kamailio.cfg should include `100.64.0.0/10` (Tailscale CGNAT range) in the source-allowlist — verify with `grep 100.64.0.0 /etc/kamailio/kamailio.cfg` on VM-A.
3. **Check Kamailio journal**: `ssh sida-kam 'journalctl -u kamailio -n 50 --no-pager | grep kamedge'`. Each successful REGISTER prints a line `[kamedge] gateway REGISTER from 100.126.178.27:5060 -> stored`. A 403 reject prints `[kamedge] reject REGISTER from <ip>:<port> (not gateway)`.

## Cross-references

- [`Docs/pilot/04_GUIDE_Office_Gateway_Setup.md`](../../Docs/pilot/04_GUIDE_Office_Gateway_Setup.md) — first-time gateway provisioning runbook
- [`Docs/pilot/05_OPERATIONAL_RUNBOOK.md`](../../Docs/pilot/05_OPERATIONAL_RUNBOOK.md) — day-to-day operations
- [`Docs/phase2/11_GUIDE_Stage_1_Closure.md`](../../Docs/phase2/11_GUIDE_Stage_1_Closure.md) §8.4 — Pattern A vs B decision record
- [`deploy/kamailio/kamailio.cfg`](../kamailio/kamailio.cfg) — the Kamailio side of the Pattern A pair (htable + REGISTER handler + outbound route)
