# deploy/dialogue-engine

Deployment artifacts for the **telephony-llm** dialogue service (`services/dialogue-engine/`) running on Kyo's hourly-rented GPU VPS.

See [`Docs/phase4/05_GUIDE_VPS_Deployment.md`](../../Docs/phase4/05_GUIDE_VPS_Deployment.md) for the topology + lifecycle context.

## Files

| File | Role |
| --- | --- |
| `telephony-llm.service` | systemd unit. Installed at `/etc/systemd/system/telephony-llm.service` on the VPS. Runs as a dedicated `telephony-llm` Linux user. |
| `install.sh` | Per-VPS install / refresh script. Idempotent. Called by `deploy/vps/deploy-all.sh`. Handles: apt deps, user creation, code rsync, venv + vLLM install, model download (first time), env seed, unit install. |
| `env.example` | Template for `/workspace/telephony-llm/config/.env`. Real `.env` is gitignored and only lives on the VPS. |
| `push.ps1` | (TODO follow-up) laptop-side rsync to a live VPS for incremental code updates between full re-installs. |

## Quick reference

### First-time install on a fresh VPS

```bash
# From /workspace on the VPS:
rsync -avz <laptop>:services/dialogue-engine/ /workspace/_src/dialogue-engine/
sudo bash /workspace/_src/dialogue-engine/deploy/dialogue-engine/install.sh
# Edit /workspace/telephony-llm/config/.env to set RAG_AUTH_TOKEN
systemctl start telephony-llm
curl http://localhost:8020/health
```

### Subsequent spinups (fast path)

Use `deploy/vps/deploy-all.sh` instead — it skips work that's already done.

## What lives where on the VPS

```
/workspace/telephony-llm/
├── .venv/                   Python venv (persistent, ~3 GB w/ vLLM)
├── dialogue_engine/         Our FastAPI app (rsync'd by install.sh)
├── config/.env              Secrets (gitignored; seeded from env.example)
├── models/                  vLLM model cache (Vikhr 8B AWQ ≈ 6 GB)
└── logs/                    Journald handles main logs; this is overflow

/etc/systemd/system/telephony-llm.service   (ephemeral; reinstalled per spinup)
```

## Local dev

You do not need to install this on your laptop. The service runs locally for development via:

```bash
cd services/dialogue-engine
uvicorn dialogue_engine.server:app --reload --port 8020
```

with the mock RAG + mock LLM clients (no GPU required). See `services/dialogue-engine/README.md`.
