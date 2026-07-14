#!/bin/bash
# AZIZA Deployment Rollback Script
# Rolls back to a previous commit or PM2 snapshot.
#
# Usage:
#   ./rollback.sh --snapshot          # Rollback to last PM2 save
#   ./rollback.sh --commit <sha>      # Rollback to specific git commit
#   ./rollback.sh --list              # List recent commits
#   ./rollback.sh --dry-run           # Show what would be done

set -euo pipefail

BUILD_DIR="/root/aziza-build"
PM2_CONFIG="$BUILD_DIR/configs/pm2/ecosystem.config.js"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[rollback]${NC} $1"; }
warn() { echo -e "${YELLOW}[rollback]${NC} $1"; }
err() { echo -e "${RED}[rollback]${NC} $1"; }

DRY_RUN=false
ACTION=""
COMMIT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --snapshot)  ACTION="snapshot"; shift ;;
        --commit)    ACTION="commit"; COMMIT="$2"; shift 2 ;;
        --list)      ACTION="list"; shift ;;
        --dry-run)   DRY_RUN=true; shift ;;
        *)           err "Unknown option: $1"; exit 1 ;;
    esac
done

if [ -z "$ACTION" ]; then
    echo "Usage: $0 [--snapshot | --commit <sha> | --list | --dry-run]"
    exit 1
fi

# ── List recent commits ──
if [ "$ACTION" == "list" ]; then
    log "Recent commits in aziza-build:"
    cd "$BUILD_DIR"
    git log --oneline -20 2>/dev/null || warn "Not a git repo"
    exit 0
fi

# ── Rollback to PM2 snapshot ──
if [ "$ACTION" == "snapshot" ]; then
    log "Rolling back to last PM2 snapshot..."
    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would run: pm2 resurrect"
        exit 0
    fi

    pm2 resurrect 2>/dev/null
    if [ $? -eq 0 ]; then
        log "PM2 processes restored from snapshot"
        pm2 status
    else
        err "No PM2 snapshot found. Use 'pm2 save' to create one first."
        exit 1
    fi
    exit 0
fi

# ── Rollback to specific commit ──
if [ "$ACTION" == "commit" ]; then
    if [ -z "$COMMIT" ]; then
        err "Commit SHA required: $0 --commit <sha>"
        exit 1
    fi

    cd "$BUILD_DIR"
    log "Checking commit $COMMIT..."
    if ! git cat-file -e "$COMMIT" 2>/dev/null; then
        err "Invalid commit: $COMMIT"
        exit 1
    fi

    log "Commit info:"
    git log --oneline -1 "$COMMIT"

    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would:"
        log "  1. git checkout $COMMIT -- ."
        log "  2. Rebuild API gateway"
        log "  3. Restart PM2 services"
        exit 0
    fi

    # Save current state
    log "Saving current state..."
    git stash 2>/dev/null || true

    # Checkout specific commit
    log "Checking out $COMMIT..."
    git checkout "$COMMIT" -- .

    # Rebuild
    log "Rebuilding API gateway..."
    (cd "$BUILD_DIR/backend/services/api-gateway" && npm install && npm run build 2>&1 | tail -5)

    # Restart services
    log "Restarting services..."
    pm2 delete all 2>/dev/null || true
    sleep 2
    pm2 start "$PM2_CONFIG"
    sleep 5
    pm2 save 2>/dev/null || true

    log "Rollback complete. Services:"
    pm2 status
    exit 0
fi
