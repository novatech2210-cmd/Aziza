#!/usr/bin/env bash
# Per-VPS install / refresh of the telephony-llm dialogue service.
#
# Idempotent: safe to re-run on every VPS spinup. Only does the slow parts
# (venv setup, model download) when something is missing.
#
# Called by deploy/vps/deploy-all.sh. Can also be invoked standalone:
#
#     sudo bash deploy/dialogue-engine/install.sh
#
# Requires:
#   - /workspace/_src/dialogue-engine/ — code from your laptop's
#     services/dialogue-engine/ (rsync'd up by deploy/vps/deploy-all.sh).
#   - root or sudo.
#   - apt-based distro (Debian/Ubuntu; vast.ai/RunPod default).
#   - NVIDIA GPU + driver + CUDA already on the host (provider-managed).

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE=/workspace
SVC_HOME="$WORKSPACE/telephony-llm"
SVC_SRC="$WORKSPACE/_src/dialogue-engine"
SVC_USER=telephony-llm
SVC_GROUP=telephony-llm
UNIT_FILE=/etc/systemd/system/telephony-llm.service
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
step() { echo -e "\033[36m[install-telephony-llm] $*\033[0m"; }
ok()   { echo -e "\033[32m[ok] $*\033[0m"; }
note() { echo -e "\033[90m    $*\033[0m"; }
fail() { echo -e "\033[31m[err] $*\033[0m" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
[ "$EUID" -eq 0 ] || fail "must run as root (or via sudo)"
[ -d "$SVC_SRC" ] || fail "source tree missing: $SVC_SRC — did you rsync from your laptop?"

# ---------------------------------------------------------------------------
# 1. System packages (idempotent — apt is fast when nothing's missing)
# ---------------------------------------------------------------------------
step "ensuring system packages"
apt-get update -qq
apt-get install -qq -y \
    python3 python3-venv python3-pip \
    ffmpeg \
    curl ca-certificates \
    rsync
ok "system packages OK"

# ---------------------------------------------------------------------------
# 2. Service user (idempotent)
# ---------------------------------------------------------------------------
if ! id -u "$SVC_USER" >/dev/null 2>&1; then
    step "creating user $SVC_USER"
    useradd --system --shell /usr/sbin/nologin --home "$SVC_HOME" "$SVC_USER"
fi
ok "user $SVC_USER present"

# ---------------------------------------------------------------------------
# 3. Directory layout (persistent, in /workspace)
# ---------------------------------------------------------------------------
step "ensuring directory layout under $SVC_HOME"
mkdir -p "$SVC_HOME"/{config,models,logs}
ok "layout OK"

# ---------------------------------------------------------------------------
# 4. Sync code (rsync from /workspace/_src to live tree)
# ---------------------------------------------------------------------------
step "rsync code: $SVC_SRC -> $SVC_HOME/dialogue_engine"
rsync -a --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.venv' \
    --exclude='tests/' \
    "$SVC_SRC/dialogue_engine/" "$SVC_HOME/dialogue_engine/"
# pyproject + Dockerfile for reference (not used at runtime)
cp -f "$SVC_SRC/pyproject.toml" "$SVC_HOME/pyproject.toml"
ok "code synced"

# ---------------------------------------------------------------------------
# 5. Python venv + deps (heavy first time — vLLM is ~3 GB of wheels)
# ---------------------------------------------------------------------------
if [ ! -f "$SVC_HOME/.venv/bin/python" ]; then
    step "creating venv (first time — installs vLLM 0.7.3 + matched torch/transformers, ~3 GB)"
    python3 -m venv "$SVC_HOME/.venv"
    "$SVC_HOME/.venv/bin/pip" install --upgrade pip
    # Pin a known-good vLLM 0.7.3 stack for CUDA 12.4 wheels (forward-compatible
    # with driver 12.x). vLLM unpinned resolves to the latest (currently 0.22 +
    # torch 2.11 + cu130 nvidia libs) which fails on driver 12.8 AND pulls
    # transformers 5.x that's incompatible with vLLM's tokenizer caching API.
    "$SVC_HOME/.venv/bin/pip" install \
        torch==2.5.1 torchaudio==2.5.1 torchvision==0.20.1 \
        --index-url https://download.pytorch.org/whl/cu124
    "$SVC_HOME/.venv/bin/pip" install \
        vllm==0.7.3 \
        transformers==4.48.3 \
        tokenizers==0.21.0
    # Install our own package last (no deps that override the pins above)
    "$SVC_HOME/.venv/bin/pip" install -e "$SVC_HOME" --no-deps
    "$SVC_HOME/.venv/bin/pip" install fastapi uvicorn[standard] pydantic httpx
    ok "venv created"
else
    step "venv exists — refreshing package install (fast)"
    "$SVC_HOME/.venv/bin/pip" install -q -e "$SVC_HOME" --no-deps
    ok "venv refreshed"
fi

# ---------------------------------------------------------------------------
# 6. Env file (don't overwrite if already exists; user populates from .env.example)
# ---------------------------------------------------------------------------
if [ ! -f "$SVC_HOME/config/.env" ]; then
    step "seeding $SVC_HOME/config/.env from env.example (EDIT BEFORE STARTING)"
    cp "$SCRIPT_DIR/env.example" "$SVC_HOME/config/.env"
    note "edit $SVC_HOME/config/.env: set RAG_URL, RAG_AUTH_TOKEN, LLM_URL"
else
    ok "config/.env exists; leaving as-is"
fi

# ---------------------------------------------------------------------------
# 7. Pre-download the LLM model (~6 GB Vikhr 8B AWQ — vLLM-native quantization)
#
# Why AWQ vs FP16: ~5 GB on disk + ~6 GB VRAM vs ~14 GB on disk + ~14 GB VRAM
# for FP16. Telephony only needs short answers; AWQ quality is fine for the
# RAG-grounded use case and saves significant resources on tight rentals.
# Switch to "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24" (FP16) here if VRAM/disk is plentiful.
# ---------------------------------------------------------------------------
MODEL_CACHE="$SVC_HOME/models"
LLM_REPO="Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24-AWQ"
LLM_LOCAL_DIR="$MODEL_CACHE/Vikhr--Vikhr-Llama-3.1-8B-Instruct-AWQ"
if [ ! -d "$LLM_LOCAL_DIR" ]; then
    step "downloading $LLM_REPO (~5 GB AWQ — slow once)"
    "$SVC_HOME/.venv/bin/pip" install -q huggingface_hub
    HF_HOME="$MODEL_CACHE" \
        "$SVC_HOME/.venv/bin/python" -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='$LLM_REPO', local_dir='$LLM_LOCAL_DIR')
print('model downloaded to $LLM_LOCAL_DIR')
"
else
    ok "model already present at $LLM_LOCAL_DIR"
fi

# ---------------------------------------------------------------------------
# 8. Ownership
# ---------------------------------------------------------------------------
chown -R "$SVC_USER:$SVC_GROUP" "$SVC_HOME"
chmod 600 "$SVC_HOME/config/.env"

# ---------------------------------------------------------------------------
# 9. systemd unit (only when systemd is the host's init — vast.ai containers
#     use a bash launcher as PID 1, so skip there and the caller starts the
#     service manually via nohup).
# ---------------------------------------------------------------------------
if systemctl is-system-running >/dev/null 2>&1 || \
   [ "$(systemctl is-system-running 2>/dev/null)" = "running" ] || \
   [ "$(systemctl is-system-running 2>/dev/null)" = "degraded" ]; then
    step "installing systemd unit"
    cp "$SCRIPT_DIR/telephony-llm.service" "$UNIT_FILE"
    chown root:root "$UNIT_FILE"
    chmod 644 "$UNIT_FILE"
    systemctl daemon-reload
    systemctl enable telephony-llm.service >/dev/null
    ok "unit installed and enabled"
    echo
    echo "Next:"
    echo "  systemctl start telephony-llm"
    echo "  curl http://localhost:8020/health"
else
    note "no functional systemd on this host (likely a container) — skipping unit install."
    note "Start vLLM first (separate background process), then start the service manually:"
    note "  sudo -u $SVC_USER bash -c 'cd $SVC_HOME && set -a && . config/.env && set +a && nohup .venv/bin/python -m dialogue_engine > logs/server.log 2>&1 &'"
    note "  curl http://localhost:8020/health"
fi
