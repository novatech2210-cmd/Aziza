#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Aziza Full Deploy — runs ON the remote server after rsync
# Usage: bash /root/aziza-deployment/deploy_to_vast.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
LOG=/var/log/aziza_deploy.log
exec > >(tee -a "$LOG") 2>&1

echo "=============================="
echo " AZIZA DEPLOY — $(date)"
echo "=============================="

# ── 1. System deps ────────────────────────────────────────────────────────────
echo "[1/8] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  curl wget git build-essential \
  redis-server \
  python3-pip python3-venv python3-dev \
  nodejs npm \
  ffmpeg libsndfile1 sox \
  supervisor

# ── 2. Node / npm version ─────────────────────────────────────────────────────
echo "[2/8] Upgrading Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - -qq
apt-get install -y -qq nodejs
npm install -g pm2 --silent

# ── 3. Ollama ────────────────────────────────────────────────────────────────
echo "[3/8] Installing Ollama..."
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

# Start Ollama as a background service
pkill ollama 2>/dev/null || true
nohup ollama serve > /var/log/ollama.log 2>&1 &
echo "Waiting for Ollama to be ready..."
for i in $(seq 1 30); do
  curl -s http://localhost:11434/api/tags &>/dev/null && break
  sleep 2
done
echo "Pulling llama3 model (background)..."
nohup ollama pull llama3 > /var/log/ollama_pull.log 2>&1 &

# ── 4. Redis ─────────────────────────────────────────────────────────────────
echo "[4/8] Starting Redis..."
service redis-server start || redis-server --daemonize yes
redis-cli ping || { echo "Redis failed!"; exit 1; }

# ── 5. Python venv + deps ─────────────────────────────────────────────────────
echo "[5/8] Building Python venv..."
python3 -m venv /root/venv
source /root/venv/bin/activate
pip install --upgrade pip --quiet

pip install --quiet \
  redis==5.0.8 \
  fastapi uvicorn[standard] \
  httpx \
  motor pymongo \
  python-dotenv \
  structlog \
  numpy \
  torch torchvision torchaudio \
  huggingface_hub \
  sphn==0.1.10 \
  sentencepiece \
  moshi \
  aiohttp

# ── 6. NestJS API Gateway ────────────────────────────────────────────────────
echo "[6/8] Building NestJS API Gateway..."
cd /root/aziza-deployment/services/api-gateway
npm ci --silent
npm run build

# ── 7. Write env files ────────────────────────────────────────────────────────
echo "[7/8] Writing environment files..."
# API Gateway
cat > /root/aziza-deployment/services/api-gateway/.env <<'ENV'
PORT=8080
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
MONGO_URI=mongodb://127.0.0.1:27017/aziza
JWT_SECRET=${JWT_SECRET:?JWT_SECRET not set}
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434
OLLAMA_MODEL=llama3
ENV

# Moshi worker
cat > /root/aziza-deployment/services/moshi-worker/.env <<'ENV'
REDIS_URL=redis://127.0.0.1:6379
OLLAMA_API_URL=http://127.0.0.1:11434/api/chat
OLLAMA_MODEL=llama3
PYTHONUNBUFFERED=1
ENV

# Orchestrator
cat > /root/aziza-deployment/services/orchestrator/.env <<'ENV'
REDIS_URL=redis://127.0.0.1:6379
PERSONA_PLEX_URL=http://127.0.0.1:8001
PYTHONUNBUFFERED=1
ENV

# ── 8. PM2 ecosystem ─────────────────────────────────────────────────────────
echo "[8/8] Starting services with PM2..."
cat > /root/aziza-deployment/ecosystem.config.js <<'PM2'
const VENV = '/root/venv/bin/python3';

module.exports = {
  apps: [
    {
      name: 'api-gateway',
      cwd: '/root/aziza-deployment/services/api-gateway',
      script: 'dist/main.js',
      interpreter: 'node',
      env_file: '.env',
      restart_delay: 3000,
      max_restarts: 10,
    },
    {
      name: 'moshi-worker',
      cwd: '/root/aziza-deployment/services/moshi-worker',
      script: 'moshi_service.py',
      interpreter: VENV,
      env_file: '.env',
      restart_delay: 5000,
      max_restarts: 5,
    },
    {
      name: 'orchestrator',
      cwd: '/root/aziza-deployment/services/orchestrator',
      script: 'main.py',
      interpreter: VENV,
      env_file: '.env',
      restart_delay: 5000,
      max_restarts: 10,
    },
  ],
};
PM2

pm2 delete all 2>/dev/null || true
pm2 start /root/aziza-deployment/ecosystem.config.js
pm2 save

echo ""
echo "=============================="
echo " DEPLOY COMPLETE ✅"
echo " API Gateway → http://localhost:8080"
echo " Ollama model pull: tail -f /var/log/ollama_pull.log"
echo "=============================="
pm2 list
