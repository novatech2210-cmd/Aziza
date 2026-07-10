# deploy/aziza-web

Deployment artifacts for **Kyo's `aziza-web` backend**, deployed FROM OUR SIDE onto the hourly GPU VPS.

Kyo writes the code (mirrored read-only at `external/aziza-web/`, gitignored). **We own the deploy** — packaging, env config, systemd unit, persistent-volume layout — so the VPS only depends on artifacts we control. Kyo's project is not modified.

See [`Docs/phase4/05_GUIDE_VPS_Deployment.md`](../../Docs/phase4/05_GUIDE_VPS_Deployment.md) for topology + lifecycle.

## Files

| File | Role |
| --- | --- |
| `aziza-web.service` | systemd unit. Installed at `/etc/systemd/system/aziza-web.service`. Runs as `aziza-web` user, listens on `:8000`. |
| `install.sh` | Per-VPS install / refresh. Idempotent. Bootstraps Postgres at `/workspace/aziza-web/postgres-data/`, creates the `aziza`/`aziza_db` role/db, installs faster-whisper + FAISS + sentence-transformers, syncs Kyo's code from `/workspace/_src/aziza-web/backend/`, seeds env. |
| `env.example` | Template for `/workspace/aziza-web/config/.env`. **Strong-secret reminder**: replace the `JWT_SECRET` and `GEMINI_API_KEY` defaults before any deploy — Kyo's repo ships known-weak defaults. |
| `push.ps1` | (follow-up) laptop-side rsync of `external/aziza-web/backend/` to a live VPS, for shipping his updates after he releases a new version on GitHub. |

## Quick reference

### First-time install on a fresh VPS

```bash
# From your laptop (push the source):
rsync -avz external/aziza-web/ <vps>:/workspace/_src/aziza-web/

# On the VPS:
sudo bash /workspace/_src/aziza-web/../../deploy/aziza-web/install.sh
# (the actual path depends on how you laid out the deploy/ subtree)

# Edit /workspace/aziza-web/config/.env: set JWT_SECRET + GEMINI_API_KEY
systemctl start aziza-web
curl http://localhost:8000/health
```

### Subsequent spinups

Use `deploy/vps/deploy-all.sh` instead.

## What lives where on the VPS

```
/workspace/aziza-web/
├── .venv/                   Python venv (persistent, ~2 GB)
├── backend/                 Kyo's FastAPI app (rsync'd by install.sh)
├── config/.env              Secrets (gitignored; seeded from env.example)
├── rag_index/               FAISS index + metadata (persistent corpus)
├── models/                  HF cache: fasttext lid.176.bin + Whisper-CT2 + embedder
├── postgres-data/           Postgres data dir (persistent across VPS stops)
└── logs/                    Overflow logs

/etc/systemd/system/aziza-web.service   (ephemeral; re-installed per spinup)

Ports:
  :5432   Postgres        (localhost-only)
  :8000   aziza-web       (our dialogue-engine calls this for RAG)
```

## Security follow-ups for Kyo (still open)

From the 2026-05-22 review of his repo:

1. **Live Gemini API key in `config.py:35`** — rotate, move to env-only, audit usage.
2. **JWT secret default `qube-phase4-secret-change-me`** — never deploy without override.
3. **DB password default `qb_password`** — `install.sh` overrides via `AZIZA_PG_PASSWORD` env at install time.

The `env.example` here calls each out. Don't leave defaults in any production deploy.
