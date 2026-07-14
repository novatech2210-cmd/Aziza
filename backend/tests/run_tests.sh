#!/bin/bash
# AZIZA E2E Test Pipeline
# Runs all test suites in the correct order and reports results.
#
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh --unit       # Unit tests only
#   ./run_tests.sh --e2e        # E2E tests only
#   ./run_tests.sh --load       # Load tests only
#   ./run_tests.sh --health     # Health checks only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$SCRIPT_DIR/../services/api-gateway"
LOAD_DIR="$SCRIPT_DIR/load"
PASS=0
FAIL=0
TOTAL=0
START_TIME=$(date +%s)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

run_suite() {
    local name="$1"
    local cmd="$2"
    local dir="${3:-.}"
    TOTAL=$((TOTAL + 1))

    echo -e "\n${YELLOW}━━━ $name ━━━${NC}"
    if (cd "$dir" && eval "$cmd") 2>&1; then
        echo -e "${GREEN}  PASS${NC}: $name"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}  FAIL${NC}: $name"
        FAIL=$((FAIL + 1))
    fi
}

echo "╔══════════════════════════════════════════╗"
echo "║      AZIZA E2E Test Pipeline             ║"
echo "╚══════════════════════════════════════════╝"
echo "Started at: $(date)"
echo ""

MODE="${1:---all}"

# ── 1. Service Health Checks ──────────────────────────────────────────
if [[ "$MODE" == "--all" || "$MODE" == "--health" || "$MODE" == "--load" ]]; then
    run_suite "vLLM Health Check" "python3 $LOAD_DIR/quick_check.py"
fi

# ── 2. Unit Tests ─────────────────────────────────────────────────────
if [[ "$MODE" == "--all" || "$MODE" == "--unit" ]]; then
    run_suite "Unit Tests (API Gateway)" "JWT_SECRET=test_secret npm test" "$GATEWAY_DIR"
fi

# ── 3. Integration Tests ──────────────────────────────────────────────
if [[ "$MODE" == "--all" || "$MODE" == "--e2e" ]]; then
    run_suite "E2E Tests (Auth + Admin + Chat)" "JWT_SECRET=test_secret npm run test:e2e" "$GATEWAY_DIR"
fi

# ── 4. Load Tests (optional, requires vLLM running) ───────────────────
if [[ "$MODE" == "--all" || "$MODE" == "--load" ]]; then
    if curl -sf http://127.0.0.1:8002/v1/models > /dev/null 2>&1; then
        run_suite "Load Test (5 concurrent, 15s)" \
            "python3 $LOAD_DIR/load_test.py --port 8002 --concurrent 5 --duration 15 --message 'Привет'"
    else
        echo -e "${YELLOW}  SKIP${NC}: Load test (vLLM not reachable on port 8002)"
    fi
fi

# ── 5. TypeScript Compilation ─────────────────────────────────────────
if [[ "$MODE" == "--all" || "$MODE" == "--unit" ]]; then
    run_suite "TypeScript Compilation" "npx tsc --noEmit" "$GATEWAY_DIR"
fi

# ── 6. Build ──────────────────────────────────────────────────────────
if [[ "$MODE" == "--all" || "$MODE" == "--unit" ]]; then
    run_suite "NestJS Build" "npx nest build" "$GATEWAY_DIR"
fi

# ── Summary ───────────────────────────────────────────────────────────
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║              RESULTS SUMMARY             ║"
echo "╠══════════════════════════════════════════╣"
echo -e "║  Total suites:  $TOTAL"
echo -e "║  ${GREEN}Passed:         $PASS${NC}"
if [ $FAIL -gt 0 ]; then
    echo -e "║  ${RED}Failed:         $FAIL${NC}"
else
    echo -e "║  Failed:         0"
fi
echo -e "║  Duration:      ${DURATION}s"
echo "╚══════════════════════════════════════════╝"

if [ $FAIL -gt 0 ]; then
    echo -e "\n${RED}OVERALL: FAIL${NC}"
    exit 1
else
    echo -e "\n${GREEN}OVERALL: PASS${NC}"
    exit 0
fi
