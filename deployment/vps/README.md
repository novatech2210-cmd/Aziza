# deploy/vps

Orchestration scripts for the **hourly-rented GPU VPS** (vast.ai / RunPod / similar) that hosts BOTH:

- Kyo's `aziza-web` (RAG + his chat module) — via [`deploy/aziza-web/`](../aziza-web/)
- Our `dialogue-engine` (vLLM + Vikhr 8B) — via [`deploy/dialogue-engine/`](../dialogue-engine/)

Read [`Docs/phase4/05_GUIDE_VPS_Deployment.md`](../../Docs/phase4/05_GUIDE_VPS_Deployment.md) for the topology + lifecycle.

## Files

| File | Role |
| --- | --- |
| `bootstrap.sh` | **First-time setup** for a brand-new VPS account. System-level prep that only runs once. |
| `deploy-all.sh` | **Per-session deploy.** Idempotent. Runs on every VPS spinup — fast when nothing's changed, full install when starting from clean `/workspace`. |
| `push-sources.ps1` | **Laptop-side.** rsyncs the two source trees (`external/aziza-web/` and `services/dialogue-engine/`) to the VPS's `/workspace/_src/`. Run from your laptop before kicking off `deploy-all.sh` on the VPS. |

## Workflow

### Day-zero (once per VPS rental account)

```bash
# 1. Start the VPS (vast.ai / RunPod UI).
# 2. SSH in.
ssh -p <port> root@<host>

# 3. Bootstrap.
mkdir -p /workspace/_src
# ... rsync deploy/ and the two source trees from your laptop (see push-sources.ps1)

# 4. First-time setup.
cd /workspace/_src/deploy/vps
sudo ./bootstrap.sh        # ~5 min: apt-get, postgres, NVIDIA toolkit verify
sudo ./deploy-all.sh       # ~10 min first time (vLLM install + Vikhr 8B download)
```

### Every-day workflow (start a session)

```bash
# 1. Start the VPS.
# 2. From your laptop, push any code updates:
.\deploy\vps\push-sources.ps1 -RemoteHost <vps-alias>

# 3. SSH in and deploy.
ssh -p <port> root@<host>
cd /workspace/_src/deploy/vps
sudo ./deploy-all.sh       # ~30-60s when state is warm

# 4. Verify both services healthy.
curl http://localhost:8000/health     # aziza-web
curl http://localhost:8020/health     # dialogue-engine

# 5. Optional: expose to telephony VM via CloudFlare tunnel.
cloudflared tunnel --url http://localhost:8020 &
# Copy the printed URL into telephony's adapter config:
#   /opt/adapter/config/dialogue.json → "url": "https://<random>.trycloudflare.com"

# 6. Do work.

# 7. When done: stop the VPS from the provider UI.
#    /workspace/ persists; root FS doesn't matter.
```

## What's idempotent vs first-time

| Step | First time | Subsequent |
| --- | --- | --- |
| apt-get install | ~3 min | <5s (cached) |
| Postgres init + cluster move to /workspace | ~30s | skipped |
| aziza-web venv install (~2 GB) | ~3 min | skipped if .venv/ exists |
| dialogue-engine venv install (~3 GB w/ vLLM) | ~5 min | skipped if .venv/ exists |
| Vikhr 8B AWQ download (~6 GB) | ~5-10 min on first call | skipped (cached in /workspace/telephony-llm/models/) |
| systemd unit install + reload | ~1s | ~1s (re-installs every spinup; root FS ephemeral) |
| systemctl start aziza-web && telephony-llm | ~30s (Whisper/FAISS load) + ~60s (vLLM warm) | same |

## Persistent state (lives in `/workspace`)

| Path | Contents | Why persistent |
| --- | --- | --- |
| `/workspace/aziza-web/.venv` | Python venv for Kyo's backend | ~2 GB; expensive to reinstall |
| `/workspace/aziza-web/postgres-data/` | Postgres data dir | corpus + users + chat history |
| `/workspace/aziza-web/rag_index/` | FAISS index + chunks JSON | the entire corporate knowledge base |
| `/workspace/aziza-web/models/` | Whisper-CT2 + bge-m3 + lid.176.bin | ~3 GB of model weights |
| `/workspace/telephony-llm/.venv` | Python venv with vLLM | ~3 GB |
| `/workspace/telephony-llm/models/` | Vikhr 8B AWQ | ~6 GB |
| `/workspace/_src/aziza-web/` | Kyo's source (synced from your laptop) | source-of-truth handoff |
| `/workspace/_src/dialogue-engine/` | Our source (synced from your laptop) | source-of-truth handoff |

## Recovery / debugging

| Symptom | Fix |
| --- | --- |
| Services don't start after `deploy-all.sh` | `systemctl status aziza-web telephony-llm` + `journalctl -u aziza-web -u telephony-llm -n 100` |
| Postgres won't start | check `journalctl -u postgresql`; data dir owner must be `postgres` (uid 999 on Debian) |
| vLLM OOM on Vikhr 8B | drop to lighter model in `/workspace/telephony-llm/config/.env` → `LLM_MODEL=uzlm/alloma-3B-Instruct`; restart |
| Cloudflare tunnel URL expired | re-run `cloudflared tunnel --url http://localhost:8020 &`; update adapter config |
| `/workspace` lost between spinups | provider issue — confirm volume attached; if first run on a new instance, re-run `bootstrap.sh` |
