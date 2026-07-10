#!/usr/bin/env bash
# Per-spinup VPS deploy. Idempotent — runs every time the VPS starts.
# Brings up Kyo's aziza-web + our dialogue-engine + their dependencies.

set -euo pipefail

step() { echo -e "\033[36m[deploy-all] $*\033[0m"; }
ok()   { echo -e "\033[32m[ok] $*\033[0m"; }
note() { echo -e "\033[90m    $*\033[0m"; }
fail() { echo -e "\033[31m[err] $*\033[0m" >&2; exit 1; }

[ "$EUID" -eq 0 ] || fail "must run as root"
[ -d /workspace ] || fail "/workspace not mounted; run bootstrap.sh first"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# 1. Verify source trees are present (rsync'd by laptop-side push-sources.ps1)
# ---------------------------------------------------------------------------
step "verifying source trees in /workspace/_src/"
[ -d /workspace/_src/aziza-web/backend ] || \
    fail "/workspace/_src/aziza-web/backend missing — run push-sources.ps1 from your laptop"
[ -d /workspace/_src/dialogue-engine/dialogue_engine ] || \
    fail "/workspace/_src/dialogue-engine/dialogue_engine missing — run push-sources.ps1"
ok "sources present"

# ---------------------------------------------------------------------------
# 2. Install/refresh aziza-web (Kyo's backend)
# ---------------------------------------------------------------------------
step "deploying aziza-web (Kyo's backend)"
bash "$DEPLOY_ROOT/aziza-web/install.sh"
ok "aziza-web install done"

# ---------------------------------------------------------------------------
# 3. Install/refresh telephony-llm (our dialogue service)
# ---------------------------------------------------------------------------
step "deploying telephony-llm (dialogue-engine + vLLM)"
bash "$DEPLOY_ROOT/dialogue-engine/install.sh"
ok "telephony-llm install done"

# ---------------------------------------------------------------------------
# 4. Start both services
# ---------------------------------------------------------------------------
step "starting services"
systemctl restart aziza-web
systemctl restart telephony-llm
ok "services restarted"

# ---------------------------------------------------------------------------
# 5. Wait for health endpoints (with reasonable per-service budgets)
# ---------------------------------------------------------------------------
wait_health() {
    local name="$1" url="$2" budget="$3"
    step "waiting for $name health ($url, up to ${budget}s)"
    for ((i=0; i<budget; i++)); do
        if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
            ok "$name healthy"
            return 0
        fi
        sleep 1
    done
    fail "$name did not become healthy within ${budget}s. Check: journalctl -u $name -n 100"
}

# aziza-web is heaviest at startup (Whisper + sentence-transformers + RAG load).
# Allow 120s for cold start. Subsequent restarts are faster.
wait_health "aziza-web"     "http://localhost:8000/health" 120

# telephony-llm waits for vLLM model load (~30-60s on Vikhr 8B AWQ once warm).
wait_health "telephony-llm" "http://localhost:8020/health" 180

# ---------------------------------------------------------------------------
# 6. Summary
# ---------------------------------------------------------------------------
echo
echo "Deploy complete. Both services up."
echo
echo "  aziza-web         http://localhost:8000  (RAG, chat, vision)"
echo "  telephony-llm     http://localhost:8020  (dialogue endpoint)"
echo
echo "To expose telephony-llm to the adapter VM:"
echo "  cloudflared tunnel --url http://localhost:8020 &"
echo "(copy the printed URL into /opt/adapter/config/dialogue.json on the adapter side)"
