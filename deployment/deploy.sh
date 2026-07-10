#!/usr/bin/env bash
#
# deploy.sh — Apply the Aziza backend fixes to /root/aziza-build
#
# Usage:
#   bash deploy.sh              # apply everything
#   bash deploy.sh --check      # pre-flight check only, no changes
#   bash deploy.sh --gateway    # only the chat.gateway.ts fix
#   bash deploy.sh --proxy      # only the ollama_proxy.py fix
#   bash deploy.sh --frontend   # only the frontend client fix
#   bash deploy.sh --ecosystem  # only the ecosystem.config.js fix
#   bash deploy.sh --vllm       # only restart vLLM with correct models
#
# Safe to re-run. Always backs up before overwriting.
# Rollback:  bash rollback.sh
#
set -euo pipefail

# ─── Paths ──────────────────────────────────────────────────────────────────
AZIZA_ROOT="/root/aziza-build"
GATEWAY_SRC="$AZIZA_ROOT/backend/services/api-gateway/src/gateway/chat.gateway.ts"
GATEWAY_DIR="$AZIZA_ROOT/backend/services/api-gateway"
ECOSYSTEM="$AZIZA_ROOT/ecosystem.config.js"
PROXY_FILE="$AZIZA_ROOT/ollama_proxy.py"
FRONTEND_DIR="$AZIZA_ROOT/frontend/src"
BACKUP_DIR="$AZIZA_ROOT/.fixes-backup-$(date +%Y%m%d-%H%M%S)"

# Source of truth — the fixed files alongside this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Helpers ────────────────────────────────────────────────────────────────
log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn ]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }
ok()   { printf '\033[1;32m[ok   ]\033[0m %s\n' "$*"; }

backup_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    mkdir -p "$BACKUP_DIR"
    cp -v "$f" "$BACKUP_DIR/$(basename "$f").bak"
  fi
}

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (need write access to $AZIZA_ROOT)."
    exit 1
  fi
}

require_file() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    err "Missing fixed file: $f"
    err "Did you copy the aziza-fixes directory to this server?"
    exit 1
  fi
}

# ─── Pre-flight check ───────────────────────────────────────────────────────
preflight() {
  log "Pre-flight check"
  local pass=0

  for f in "$GATEWAY_SRC" "$GATEWAY_DIR/package.json" "$AZIZA_ROOT/ecosystem.config.js"; do
    if [[ -f "$f" ]]; then ok "found: $f"; else err "missing: $f"; pass=1; fi
  done

  command -v pm2     >/dev/null && ok "pm2 found"     || { err "pm2 missing"; pass=1; }
  command -v node    >/dev/null && ok "node found"    || { err "node missing"; pass=1; }
  command -v npm     >/dev/null && ok "npm found"     || { err "npm missing"; pass=1; }
  command -v python3 >/dev/null && ok "python3 found" || { err "python3 missing"; pass=1; }

  if (( pass == 0 )); then ok "Pre-flight OK"; else err "Pre-flight failed"; exit 1; fi
}

# ─── Step 1: chat.gateway.ts ─────────────────────────────────────────────────
deploy_gateway() {
  log "Step 1: replacing chat.gateway.ts"
  require_file "$SCRIPT_DIR/chat.gateway.ts"
  backup_file "$GATEWAY_SRC"
  cp -v "$SCRIPT_DIR/chat.gateway.ts" "$GATEWAY_SRC"

  log "Rebuilding api-gateway (nest build)…"
  (cd "$GATEWAY_DIR" && npm run build)
  ok "Gateway rebuilt"
}

# ─── Step 2: ecosystem.config.js ─────────────────────────────────────────────
deploy_ecosystem() {
  log "Step 2: replacing ecosystem.config.js"
  require_file "$SCRIPT_DIR/ecosystem.config.js"
  backup_file "$ECOSYSTEM"
  cp -v "$SCRIPT_DIR/ecosystem.config.js" "$ECOSYSTEM"
  ok "ecosystem.config.js updated"
}

# ─── Step 3: ollama_proxy.py ─────────────────────────────────────────────────
deploy_proxy() {
  log "Step 3: replacing ollama_proxy.py"
  require_file "$SCRIPT_DIR/ollama_proxy.py"
  backup_file "$PROXY_FILE"
  cp -v "$SCRIPT_DIR/ollama_proxy.py" "$PROXY_FILE"
  chmod +x "$PROXY_FILE"

  # Kill any old proxy / bare ollama that might be squatting on :11434
  if pgrep -f "ollama_proxy.py" >/dev/null; then
    warn "Old ollama_proxy.py is running — restarting it"
    pkill -f "ollama_proxy.py" || true
    sleep 1
  fi
  if pgrep -x ollama >/dev/null; then
    warn "Bare 'ollama' process is running on :11434 — killing it (proxy replaces it)"
    pkill -x ollama || true
    sleep 1
  fi

  nohup python3 "$PROXY_FILE" > /var/log/ollama_proxy.log 2>&1 &
  sleep 2

  # Verify the proxy answers
  if curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
    ok "Ollama proxy responding on :11434"
  else
    err "Proxy did not start — check /var/log/ollama_proxy.log"
    exit 1
  fi
}

# ─── Step 4: frontend client ─────────────────────────────────────────────────
deploy_frontend() {
  log "Step 4: dropping frontend-chat-client.ts into $FRONTEND_DIR"
  require_file "$SCRIPT_DIR/frontend-chat-client.ts"

  # We don't know the exact import site in your frontend, so we drop the
  # reference implementation next to the existing code. Wire it into your
  # chat component by importing { socket } from './frontend-chat-client'.
  mkdir -p "$FRONTEND_DIR"
  cp -v "$SCRIPT_DIR/frontend-chat-client.ts" "$FRONTEND_DIR/lib/chat-socket.ts"

  warn "You still need to:"
  warn "  1. Find the file that currently calls io('http://localhost:8080/api/chat-text')"
  warn "     (likely under $FRONTEND_DIR)"
  warn "  2. Replace that import with: import { socket } from './lib/chat-socket'"
  warn "  3. Rebuild the frontend:  cd $AZIZA_ROOT/frontend && npm run build"
  warn "  4. pm2 restart frontend"
}

# ─── Step 5: restart PM2 services ────────────────────────────────────────────
restart_pm2() {
  log "Step 5: restarting PM2 services"
  pm2 restart api-gateway || pm2 restart ecosystem.config.js --only api-gateway
  ok "api-gateway restarted"

  # Sanity check the gateway came back up
  sleep 3
  if curl -sf http://localhost:8080/api/health >/dev/null; then
    ok "api-gateway /api/health OK"
  else
    err "api-gateway not responding — check: pm2 logs api-gateway --lines 50"
    exit 1
  fi
}

# ─── Step 6: vLLM models (manual — requires GPU + model download) ─────────────
deploy_vllm() {
  log "Step 6: vLLM model swap (interactive — requires confirmation)"

  cat <<'EOF'

The English vLLM is currently serving Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24
which is a Russian-tuned model — that's why English requests came back in Russian.

Recommended replacement:  meta-llama/Llama-3.1-8B-Instruct

For the Uzbek vLLM, the chat template is missing, which is why <|im_end|> tokens
leak into responses. Restart it with an explicit ChatML template.

EOF

  read -r -p "Proceed with swapping vLLM models now? [y/N] " yn
  case "$yn" in
    y|Y) ;;
    *) warn "Skipping vLLM swap. English answers will stay in Russian until you do this."; return 0 ;;
  esac

  # 6a. ChatML template for the Uzbek model
  cat > "$AZIZA_ROOT/chatml.jinja" <<'JINJA'
{% for message in messages %}{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>\n'}}{% endfor %}{% if add_generation_prompt %}{{'<|im_start|>assistant\n'}}{% endif %}
JINJA
  ok "Wrote $AZIZA_ROOT/chatml.jinja"

  # 6b. Stop the old vLLM processes
  pm2 stop vllm-english vllm-uzbek 2>/dev/null || true

  # 6c. Start the English vLLM with the correct model
  log "Starting vLLM English on :8002 with Llama-3.1-8B-Instruct"
  read -r -p "Use meta-llama/Llama-3.1-8B-Instruct? [Y/n] " model_yn
  model_yn=${model_yn:-Y}
  case "$model_yn" in
    n|N)
      read -r -p "Enter alternative HuggingFace model id: " EN_MODEL
      ;;
    *)
      EN_MODEL="meta-llama/Llama-3.1-8B-Instruct"
      ;;
  esac

  pm2 start "vllm serve $EN_MODEL --port 8002 --enforce-eager" \
    --name vllm-english \
    --cwd "$AZIZA_ROOT"

  # 6d. Start the Uzbek vLLM with explicit ChatML template
  log "Starting vLLM Uzbek on :8003 with ChatML template"
  pm2 start "vllm serve uzlm/alloma-3B-Instruct --port 8003 --chat-template $AZIZA_ROOT/chatml.jinja --enforce-eager" \
    --name vllm-uzbek \
    --cwd "$AZIZA_ROOT"

  pm2 save

  warn "vLLM models take 2–5 minutes to load. Check progress with:"
  warn "  pm2 logs vllm-english --lines 50"
  warn "  pm2 logs vllm-uzbek   --lines 50"
  warn "Then test:"
  warn "  curl -s http://localhost:8002/v1/chat/completions \\"
  warn "    -H 'Content-Type: application/json' \\"
  warn "    -d '{\"model\":\"$EN_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello!\"}]}' | jq .choices[0].message.content"
}

# ─── Step 7: end-to-end smoke test ────────────────────────────────────────────
smoke_test() {
  log "Step 7: end-to-end smoke test (Russian — should NOT go through drift retry)"

  # Use a small Node one-liner against the gateway
  if ! command -v node >/dev/null; then
    warn "node not found — skipping smoke test"
    return 0
  fi

  node -e '
    const WebSocket = require("ws");
    const ws = new WebSocket("ws://localhost:8080/api/chat-text?sessionId=smoketest");
    let tokens = "";
    ws.on("open", () => ws.send(JSON.stringify({ message: "Привет", language: "ru" })));
    ws.on("message", (data) => {
      const m = JSON.parse(data.toString());
      if (m.type === "token") tokens += m.content;
      if (m.type === "done")  { console.log("REPLY:", tokens); ws.close(); process.exit(0); }
      if (m.type === "error") { console.error("ERROR:", m.message); process.exit(1); }
    });
    setTimeout(() => { console.error("TIMEOUT"); process.exit(1); }, 30000);
  ' && ok "Smoke test passed" || err "Smoke test failed"
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
  require_root

  local mode="${1:-all}"
  case "$mode" in
    --check)    preflight; exit 0 ;;
    --gateway)  preflight; deploy_gateway;  restart_pm2; smoke_test ;;
    --proxy)    preflight; deploy_proxy;    smoke_test ;;
    --frontend) preflight; deploy_frontend ;;
    --ecosystem)preflight; deploy_ecosystem; restart_pm2 ;;
    --vllm)     preflight; deploy_vllm ;;
    all|"")
      preflight
      deploy_gateway
      deploy_ecosystem
      deploy_proxy
      deploy_frontend
      restart_pm2
      deploy_vllm
      smoke_test
      ;;
    *)
      err "Unknown mode: $mode"
      err "Usage: bash deploy.sh [--check|--gateway|--proxy|--frontend|--ecosystem|--vllm]"
      exit 1
      ;;
  esac

  echo
  ok "Deployment complete."
  log "Backup of original files: $BACKUP_DIR"
  log "To roll back: bash rollback.sh $BACKUP_DIR"
}

main "$@"
