#!/usr/bin/env bash
# First-time VPS bootstrap. Run once per VPS rental account.
#
# Idempotent: safe to re-run, but rarely needed — `deploy-all.sh`
# handles the per-spinup work.
#
# Assumes:
#   - Debian/Ubuntu image on vast.ai/RunPod with NVIDIA driver + CUDA.
#   - Persistent volume mounted at /workspace.
#   - root or sudo.

set -euo pipefail

step() { echo -e "\033[36m[bootstrap] $*\033[0m"; }
ok()   { echo -e "\033[32m[ok] $*\033[0m"; }
note() { echo -e "\033[90m    $*\033[0m"; }
fail() { echo -e "\033[31m[err] $*\033[0m" >&2; exit 1; }

[ "$EUID" -eq 0 ] || fail "must run as root"

# ---------------------------------------------------------------------------
# 1. Persistent volume exists
# ---------------------------------------------------------------------------
step "verifying /workspace is mounted + writable"
[ -d /workspace ] || fail "/workspace not mounted — check the VPS provider's persistent volume config"
mkdir -p /workspace/_src
touch /workspace/_src/.bootstrap-test && rm /workspace/_src/.bootstrap-test
ok "/workspace usable"

# ---------------------------------------------------------------------------
# 2. NVIDIA toolchain check
# ---------------------------------------------------------------------------
step "verifying NVIDIA driver + CUDA"
if ! command -v nvidia-smi >/dev/null 2>&1; then
    fail "nvidia-smi not found — choose a GPU image on the provider"
fi
nvidia-smi -L
ok "GPU visible to userspace"

# ---------------------------------------------------------------------------
# 3. System packages (heavy)
# ---------------------------------------------------------------------------
step "apt-get update + base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y \
    python3 python3-venv python3-dev python3-pip \
    postgresql postgresql-contrib \
    ffmpeg \
    curl wget ca-certificates \
    rsync \
    git \
    build-essential
ok "base packages installed"

# ---------------------------------------------------------------------------
# 4. Cloudflared (optional but useful for external access)
# ---------------------------------------------------------------------------
if ! command -v cloudflared >/dev/null 2>&1; then
    step "installing cloudflared (for ephemeral tunnels)"
    curl -fsSL -o /usr/local/bin/cloudflared \
        https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod +x /usr/local/bin/cloudflared
    ok "cloudflared installed"
else
    ok "cloudflared already present"
fi

# ---------------------------------------------------------------------------
# 5. Done
# ---------------------------------------------------------------------------
echo
echo "Bootstrap complete. Next:"
echo "  1. (from your laptop) Push sources:"
echo "       .\\deploy\\vps\\push-sources.ps1 -RemoteHost <this-vps>"
echo "  2. (on VPS) Run the per-spinup deploy:"
echo "       sudo bash /workspace/_src/deploy/vps/deploy-all.sh"
