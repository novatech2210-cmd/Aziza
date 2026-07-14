#!/bin/bash
# AZIZA Service Startup Script
# Starts all services in the correct order with health checks between stages.
#
# Usage:
#   ./start_services.sh              # Start all services
#   ./start_services.sh --validate   # Validate env first
#   ./start_services.sh --restart    # Restart all services
#   ./start_services.sh --status     # Show service status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="/root/aziza-build"
PM2_CONFIG="$BUILD_DIR/configs/pm2/ecosystem.config.js"
LOG_DIR="$BUILD_DIR/logs"
HEALTH_TIMEOUT=30

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $1"; }
err() { echo -e "${RED}[$(date +%H:%M:%S)] ERROR:${NC} $1"; }

check_port() {
    local port=$1 name=$2 timeout=${3:-$HEALTH_TIMEOUT}
    local elapsed=0
    while ! curl -sf "http://127.0.0.1:$port" > /dev/null 2>&1 && \
          ! curl -sf "http://127.0.0.1:$port/v1/models" > /dev/null 2>&1 && \
          ! curl -sf "http://127.0.0.1:$port/health" > /dev/null 2>&1; do
        if [ $elapsed -ge $timeout ]; then
            err "$name failed to start on port $port after ${timeout}s"
            return 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    log "$name is UP (port $port, ${elapsed}s)"
    return 0
}

ensure_dirs() {
    mkdir -p "$LOG_DIR"
}

validate_env() {
    log "Validating environment..."
    python3 "$SCRIPT_DIR/validate_env.py" --env-only
}

start_redis_mongo() {
    log "Starting Redis..."
    if ! systemctl is-active --quiet redis-server 2>/dev/null && \
       ! pgrep -x redis-server > /dev/null 2>&1; then
        redis-server --daemonize yes --loglevel warning
        sleep 1
    fi
    if redis-cli ping > /dev/null 2>&1; then
        log "Redis is UP"
    else
        err "Redis failed to start"
        exit 1
    fi

    log "Starting MongoDB..."
    if ! systemctl is-active --quiet mongod 2>/dev/null && \
       ! pgrep -x mongod > /dev/null 2>&1; then
        mongod --fork --logpath "$LOG_DIR/mongod.log" --dbpath /var/lib/mongodb 2>/dev/null || true
        sleep 2
    fi
    if mongosh --eval "db.version()" --quiet > /dev/null 2>&1; then
        log "MongoDB is UP"
    else
        warn "MongoDB may not be running — some services may fail"
    fi
}

start_services() {
    local mode="${1:-start}"

    if [ "$mode" == "restart" ]; then
        log "Stopping all PM2 services..."
        pm2 delete all 2>/dev/null || true
        sleep 2
    fi

    # Start infrastructure first
    start_redis_mongo

    # Build API gateway if needed
    if [ ! -d "$BUILD_DIR/backend/services/api-gateway/dist" ]; then
        log "Building API Gateway..."
        (cd "$BUILD_DIR/backend/services/api-gateway" && npm run build)
    fi

    # Start via PM2
    log "Starting services via PM2..."
    pm2 start "$PM2_CONFIG"

    # Wait for critical services
    sleep 3

    log "Checking service health..."
    local all_ok=true
    check_port 8080 "API Gateway" 15 || all_ok=false
    check_port 8000 "PersonaPlex" 15 || all_ok=false
    check_port 8002 "vLLM English" 60 || warn "vLLM English may still be loading"
    check_port 8003 "vLLM Uzbek" 60 || warn "vLLM Uzbek may still be loading"

    if $all_ok; then
        log "All critical services are UP"
    else
        warn "Some services failed to start — check logs"
    fi

    # Save PM2 state
    pm2 save 2>/dev/null || true

    log "Service status:"
    pm2 status
}

show_status() {
    pm2 status
}

case "${1:---start}" in
    --validate)
        validate_env
        ;;
    --restart)
        ensure_dirs
        start_services restart
        ;;
    --status)
        show_status
        ;;
    --start|*)
        ensure_dirs
        start_services start
        ;;
esac
