#!/usr/bin/env bash
# Per-VPS install / refresh of Kyo's aziza-web backend.
#
# We deploy HIS code FROM OUR SIDE. The source-of-truth is the read-only
# mirror at external/aziza-web/ in our repo (gitignored; refreshed from
# Kyo's GitHub when he ships an update).
#
# Idempotent: safe to re-run on every VPS spinup. Heavy steps (apt deps,
# Python deps, FAISS index init) only run when state is missing.
#
# Called by deploy/vps/deploy-all.sh. Can also be invoked standalone:
#
#     sudo bash deploy/aziza-web/install.sh
#
# Requires:
#   - /workspace/_src/aziza-web/ — rsync'd by deploy/vps/deploy-all.sh
#     from your laptop's external/aziza-web/.
#   - root or sudo.
#   - apt-based distro.
#   - NVIDIA GPU + CUDA already on host (provider-managed).

set -euo pipefail

# ---------------------------------------------------------------------------
WORKSPACE=/workspace
SVC_HOME="$WORKSPACE/aziza-web"
SVC_SRC="$WORKSPACE/_src/aziza-web"
SVC_USER=aziza-web
SVC_GROUP=aziza-web
UNIT_FILE=/etc/systemd/system/aziza-web.service
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Postgres (matches Kyo's config.py defaults; install.sh overrides via .env).
PG_USER=aziza
PG_PASSWORD="${AZIZA_PG_PASSWORD:?AZIZA_PG_PASSWORD not set}"
PG_DB=aziza_db

# ---------------------------------------------------------------------------
step() { echo -e "\033[36m[install-aziza-web] $*\033[0m"; }
ok()   { echo -e "\033[32m[ok] $*\033[0m"; }
note() { echo -e "\033[90m    $*\033[0m"; }
fail() { echo -e "\033[31m[err] $*\033[0m" >&2; exit 1; }

# ---------------------------------------------------------------------------
[ "$EUID" -eq 0 ] || fail "must run as root (or via sudo)"
[ -d "$SVC_SRC/backend" ] || fail "source tree missing: $SVC_SRC/backend — did you rsync external/aziza-web/ from your laptop?"

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
step "ensuring system packages (postgresql + ffmpeg + python)"
apt-get update -qq
apt-get install -qq -y \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    ffmpeg \
    curl ca-certificates rsync
ok "system packages OK"

# ---------------------------------------------------------------------------
# 2. Postgres — ensure a cluster is running, then ensure user/db exist.
#    On a "real" VPS we relocate the data dir to /workspace (persistent across
#    stops). On a vast.ai container with no systemd, we use the default cluster
#    on root FS (ephemeral — re-imported every spinup is fine for the corpus
#    size, and the test instance only lives a few hours anyway).
# ---------------------------------------------------------------------------
HAS_SYSTEMD=0
if systemctl is-system-running >/dev/null 2>&1 || \
   [ "$(systemctl is-system-running 2>/dev/null)" = "running" ] || \
   [ "$(systemctl is-system-running 2>/dev/null)" = "degraded" ]; then
    HAS_SYSTEMD=1
fi

if [ "$HAS_SYSTEMD" = "1" ]; then
    PG_DATA="$SVC_HOME/postgres-data"
    if [ ! -d "$PG_DATA/base" ]; then
        step "initializing Postgres data dir at $PG_DATA"
        mkdir -p "$PG_DATA"
        chown -R postgres:postgres "$PG_DATA"
        chmod 700 "$PG_DATA"
        sudo -u postgres /usr/lib/postgresql/*/bin/initdb -D "$PG_DATA"
        if [ -f /etc/postgresql/*/main/postgresql.conf ]; then
            sed -i "s|^data_directory.*|data_directory = '$PG_DATA'|" /etc/postgresql/*/main/postgresql.conf
        fi
    fi
    systemctl enable postgresql >/dev/null
    systemctl restart postgresql
else
    note "no systemd → using default Postgres cluster (16/main) via pg_ctlcluster"
    # Start the default cluster if not already running.
    if ! sudo -u postgres psql -tAc "SELECT 1" >/dev/null 2>&1; then
        pg_ctlcluster 16 main start || \
            sudo -u postgres /usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/16/main -l /tmp/pg.log start
    fi
fi

# Ensure user + db exist (works under either branch above)
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASSWORD';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $PG_DB OWNER $PG_USER;"
ok "Postgres up; user/db present"

# ---------------------------------------------------------------------------
# 3. Service user
# ---------------------------------------------------------------------------
if ! id -u "$SVC_USER" >/dev/null 2>&1; then
    step "creating user $SVC_USER"
    useradd --system --shell /usr/sbin/nologin --home "$SVC_HOME" "$SVC_USER"
fi
ok "user $SVC_USER present"

# ---------------------------------------------------------------------------
# 4. Directory layout
# ---------------------------------------------------------------------------
step "ensuring directory layout under $SVC_HOME"
mkdir -p "$SVC_HOME"/{config,rag_index,models,logs}
ok "layout OK"

# ---------------------------------------------------------------------------
# 5. Sync code (Kyo's backend from /workspace/_src/aziza-web/backend/)
# ---------------------------------------------------------------------------
step "rsync code: $SVC_SRC/backend -> $SVC_HOME/backend"
rsync -a --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.venv' \
    "$SVC_SRC/backend/" "$SVC_HOME/backend/"

# Patch Kyo's requirements: PyPI dropped the bare "faiss-gpu" package in 2024;
# Meta's modern Python 3.12 wheels are published as "faiss-gpu-cu12". Without
# this, pip install fails with "No matching distribution found for faiss-gpu".
sed -i 's|^faiss-gpu$|faiss-gpu-cu12|' "$SVC_HOME/backend/requirements.txt"
ok "code synced"

# ---------------------------------------------------------------------------
# 6. Python venv + Kyo's requirements.txt (heavy: faster-whisper + faiss-gpu + sentence-transformers)
# ---------------------------------------------------------------------------
if [ ! -f "$SVC_HOME/.venv/bin/python" ]; then
    step "creating venv (first time — installs faster-whisper, FAISS, sentence-transformers, ~2 GB)"
    python3 -m venv "$SVC_HOME/.venv"
    "$SVC_HOME/.venv/bin/pip" install --upgrade pip
    # Pin torch to a CUDA 12.4 wheel FIRST. Kyo's requirements.txt leaves torch
    # unpinned, so pip resolves to the newest (currently 2.12 / cu13), which
    # fails at startup with "NVIDIA driver too old (12080)" on vast.ai's
    # driver 570.211.01 (CUDA 12.8). Pinning here forces pip to skip the
    # upgrade later. cu124 wheels are forward-compatible with driver 12.x.
    # 2.6.0 is the floor: transformers 5.x refuses .pth loads on torch < 2.6
    # (CVE-2025-32434).
    "$SVC_HOME/.venv/bin/pip" install \
        torch==2.6.0 \
        --index-url https://download.pytorch.org/whl/cu124
    "$SVC_HOME/.venv/bin/pip" install -r "$SVC_HOME/backend/requirements.txt"
    "$SVC_HOME/.venv/bin/pip" install rank-bm25  # per Kyo's DEPLOY.md note
    ok "venv created"
else
    step "venv exists — refreshing pip install (fast if no new deps)"
    "$SVC_HOME/.venv/bin/pip" install -q -r "$SVC_HOME/backend/requirements.txt"
    ok "venv refreshed"
fi

# ---------------------------------------------------------------------------
# 7. Env file (seed once; user populates)
# ---------------------------------------------------------------------------
if [ ! -f "$SVC_HOME/config/.env" ]; then
    step "seeding $SVC_HOME/config/.env from env.example"
    cp "$SCRIPT_DIR/env.example" "$SVC_HOME/config/.env"
    # Substitute the postgres URL we just built into the env file.
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://$PG_USER:$PG_PASSWORD@localhost:5432/$PG_DB|" "$SVC_HOME/config/.env"
    note "edit $SVC_HOME/config/.env: set GEMINI_API_KEY, JWT_SECRET (NEVER use defaults)"
else
    ok "config/.env exists; leaving as-is"
fi

# ---------------------------------------------------------------------------
# 8. RAG index path — point Kyo's code at our persistent dir
# ---------------------------------------------------------------------------
# (Done via env var RAG_INDEX_PATH in config/.env)

# ---------------------------------------------------------------------------
# 9. Ownership
# ---------------------------------------------------------------------------
chown -R "$SVC_USER:$SVC_GROUP" "$SVC_HOME"
chmod 600 "$SVC_HOME/config/.env"

# ---------------------------------------------------------------------------
# 10. systemd unit (only if systemd is functional — vast.ai containers use a
#     bash launcher as PID 1, so this step is skipped there)
# ---------------------------------------------------------------------------
if systemctl is-system-running >/dev/null 2>&1 || [ "$(systemctl is-system-running 2>/dev/null)" = "running" ] || [ "$(systemctl is-system-running 2>/dev/null)" = "degraded" ]; then
    step "installing systemd unit"
    cp "$SCRIPT_DIR/aziza-web.service" "$UNIT_FILE"
    chown root:root "$UNIT_FILE"
    chmod 644 "$UNIT_FILE"
    systemctl daemon-reload
    systemctl enable aziza-web.service >/dev/null
    ok "unit installed and enabled"
    echo
    echo "Next:"
    echo "  systemctl start aziza-web"
    echo "  curl http://localhost:8000/health"
else
    note "no functional systemd on this host (likely a container) — skipping unit install."
    note "Start the service manually with:"
    note "  sudo -u $SVC_USER bash -c 'cd $SVC_HOME/backend && set -a && . $SVC_HOME/config/.env && set +a && nohup $SVC_HOME/.venv/bin/python server.py > $SVC_HOME/logs/server.log 2>&1 &'"
    note "  curl http://localhost:8000/health"
fi
