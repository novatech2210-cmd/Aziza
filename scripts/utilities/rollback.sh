#!/usr/bin/env bash
#
# rollback.sh — undo a deploy.sh run
#
# Usage:  bash rollback.sh [backup_dir]
#   If no backup_dir is given, uses the most recent /root/aziza-build/.fixes-backup-*
#
set -euo pipefail

AZIZA_ROOT="/root/aziza-root"
AZIZA_ROOT="/root/aziza-build"
GATEWAY_SRC="$AZIZA_ROOT/backend/services/api-gateway/src/gateway/chat.gateway.ts"
ECOSYSTEM="$AZIZA_ROOT/ecosystem.config.js"
PROXY_FILE="$AZIZA_ROOT/ollama_proxy.py"
FRONTEND_LIB="$AZIZA_ROOT/frontend/src/lib/chat-socket.ts"

log()  { printf '\033[1;36m[rollback]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok      ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn    ]\033[0m %s\n' "$*"; }

if [[ $EUID -ne 0 ]]; then
  echo "Must run as root." >&2
  exit 1
fi

# Pick the most recent backup if none specified
if [[ $# -ge 1 ]]; then
  BACKUP_DIR="$1"
else
  BACKUP_DIR=$(ls -dt "$AZIZA_ROOT"/.fixes-backup-* 2>/dev/null | head -n1)
fi

if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
  echo "No backup directory found. Nothing to roll back." >&2
  exit 1
fi

log "Using backup: $BACKUP_DIR"

restore() {
  local src="$1" dst="$2"
  if [[ -f "$src" ]]; then
    cp -v "$src" "$dst"
    ok "restored $dst"
  else
    warn "no backup for $dst — leaving the fixed version in place"
  fi
}

restore "$BACKUP_DIR/chat.gateway.ts.bak"        "$GATEWAY_SRC"
restore "$BACKUP_DIR/ecosystem.config.js.bak"    "$ECOSYSTEM"
restore "$BACKUP_DIR/ollama_proxy.py.bak"        "$PROXY_FILE"

# Rebuild the gateway from the restored source
log "Rebuilding api-gateway…"
(cd "$AZIZA_ROOT/backend/services/api-gateway" && npm run build) || warn "nest build failed — check the source file"

# Remove the new frontend lib if it was added by deploy.sh
if [[ -f "$FRONTEND_LIB" ]] && [[ ! -f "$BACKUP_DIR/chat-socket.ts.bak" ]]; then
  rm -fv "$FRONTEND_LIB"
fi

# Restart the proxy if it was running
if pgrep -f ollama_proxy.py >/dev/null; then
  pkill -f ollama_proxy.py || true
  sleep 1
fi

# Restart PM2 services from the restored ecosystem.config.js
if [[ -f "$ECOSYSTEM" ]]; then
  pm2 restart ecosystem.config.js --only api-gateway 2>/dev/null || pm2 restart api-gateway 2>/dev/null || warn "pm2 restart failed — run manually"
fi

ok "Rollback complete."
log "Note: vLLM models were not reverted — if you swapped them with deploy.sh --vllm,"
log "you need to manually restart vllm-english and vllm-uzbek with the original models."
