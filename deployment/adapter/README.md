# deploy/adapter

systemd unit for the AMD/LID adapter (project Phase 3).

> **SSH access** — `ssh sida-pbx` for VM-B (where this adapter is deployed). See [Docs/REFERENCE_Hosts_and_SSH_Aliases.md](../../Docs/REFERENCE_Hosts_and_SSH_Aliases.md) for the canonical host list.

## First-time install on VM-B

Run as root on VM-B `core-server-telephony`:

```bash
# user + dirs
adduser --system --no-create-home --group adapter
mkdir -p /opt/adapter /var/log/adapter
chown adapter:adapter /var/log/adapter

# unit
cp /path/to/repo/deploy/adapter/adapter.service /etc/systemd/system/
systemctl daemon-reload

# code lives under /opt/adapter (deployed by scripts/deploy-adapter-vmb.sh)
# config at /opt/adapter/config/{asterisk,amd,lid}.json
# models at /opt/vosk/models/{ru,en,kk}/  (downloaded by scripts/download-vosk-models.sh)
```

## Operate

```bash
systemctl enable adapter
systemctl start adapter
systemctl status adapter
journalctl -u adapter -f                  # or: tail -f /var/log/adapter/adapter.log
```

## Reload config without restart

SIGHUP config hot-reload is implemented (`main.py` → `ConfigHolder.reload`)
and the unit now has `ExecReload=/bin/kill -HUP $MAINPID` (added
2026-05-15). So a JSON config edit applies with **no dropped calls**:

```bash
systemctl reload adapter            # SIGHUP -> re-reads config/*.json
```

Use `systemctl restart adapter` only for **code** changes (Python is not
hot-reloaded by SIGHUP) or **unit** changes (after `daemon-reload`).

## Local-first IaC: push.ps1 (unit-file only)

`./push.ps1` mirrors `deploy/kamailio/push.ps1` but is **scoped to the
systemd unit file only** — stage → `systemd-analyze verify` → backup →
atomic apply → `daemon-reload` → restart → verify `:9095`.

```powershell
.\push.ps1 -DryRun      # show unit diff vs live, change nothing
.\push.ps1              # apply unit + daemon-reload + restart + verify
.\push.ps1 -NoRestart   # apply + daemon-reload, skip the ~150s restart
.\push.ps1 -Pull        # refresh local adapter.service from live VM-B
```

**It does NOT sync the Python code.** The adapter package
(`services/adapter/`) currently has in-flight, partially-uncommitted
changes (`config.py`, `main.py`, Phase-5 `web_post.py`); a blind `*.py`
sync would ship uncommitted code to production. Code deployment stays
manual (`scripts/deploy-adapter-vmb.sh`, local-only) until that is
untangled. The unit file is the stable artifact and carries the two
2026-05-15 production fixes, so it's the piece worth automating first.

Also not synced: `/opt/adapter/config/*.json` (real ARI secret;
`max_analysis_ms` / `lid.default_language` are operator-managed and
differ test-vs-prod) and `.venv` (rebuild on `pyproject.toml` change).

## Critical unit settings — do not regress

| Setting | Why | Ref |
| --- | --- | --- |
| `PrivateTmp=false` | Adapter writes `/tmp/amd-<uuid>.{amd,lid}`; Asterisk (PrivateTmp=no) reads it back via `SHELL(cat)`. A private tmp namespace breaks the handoff → every call wrongly HUMAN. | [10_REFERENCE §1](../../Docs/phase3/10_REFERENCE_VM-B_Live_AMD_Validation_2026-05-15.md) |
| `ExecReload=/bin/kill -HUP $MAINPID` | Makes `systemctl reload adapter` work for config hot-reload (06_GUIDE). | 10_REFERENCE §4 |

Both were production-blocking bugs found + fixed on 2026-05-15.

## File map

| Path on VM-B | Owner | What |
| --- | --- | --- |
| `/opt/adapter/` | `adapter:adapter` | code (rsynced from repo `services/adapter/`) |
| `/opt/adapter/.venv/` | `adapter:adapter` | virtualenv with `vosk`, `soxr` |
| `/opt/adapter/config/` | `adapter:adapter` | live config files (override repo examples) |
| `/opt/vosk/models/{ru,en,kk}/` | `root:root` (read-only) | Vosk models |
| `/var/log/adapter/adapter.log` | `adapter:adapter` | structured log |
| `/etc/systemd/system/adapter.service` | `root:root` | this unit |
