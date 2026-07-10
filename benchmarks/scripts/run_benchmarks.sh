#!/bin/bash
# Aziza Unified Benchmark Runner
# Chains all benchmarks in sequence and generates final report

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "========================================"
echo "Aziza Milestone 2 Benchmark Suite"
echo "========================================"
echo ""

# Create directories
mkdir -p reports telemetry

# Load config
CONFIG_FILE="benchmark_config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Source virtual environment if present
if [ -f "/root/aziza-build/venv312/bin/activate" ]; then
    source "/root/aziza-build/venv312/bin/activate"
elif [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Function to run a benchmark and check exit code
run_benchmark() {
    local name=$1
    local script=$2
    
    echo "----------------------------------------"
    echo "Running: $name"
    echo "----------------------------------------"
    
    if python3 "$script"; then
        echo "✓ $name PASSED"
        return 0
    else
        echo "✗ $name FAILED"
        return 1
    fi
}

# Track overall status
OVERALL_STATUS="PASS"
FAILED_BENCHMARKS=()

# Run benchmarks in sequence
echo "Starting benchmark suite..."
echo ""

# 1. E2E Integration Test
if ! run_benchmark "E2E Integration Test" "scripts/e2e_integration_test.py"; then
    FAILED_BENCHMARKS+=("e2e_integration")
    OVERALL_STATUS="FAIL"
fi
echo ""

# 2. TTFT Benchmark
if ! run_benchmark "TTFT Benchmark" "scripts/ttft_benchmark.py"; then
    FAILED_BENCHMARKS+=("ttft")
    OVERALL_STATUS="FAIL"
fi
echo ""

# 3. Text→Text Benchmark
if ! run_benchmark "Text→Text Benchmark" "scripts/text_to_text_benchmark.py"; then
    FAILED_BENCHMARKS+=("text_to_text")
    OVERALL_STATUS="FAIL"
fi
echo ""

# 4. Voice→Text Validation
if ! run_benchmark "Voice→Text Validation" "scripts/voice_to_text_validation.py"; then
    FAILED_BENCHMARKS+=("voice_to_text")
    OVERALL_STATUS="FAIL"
fi
echo ""

# 5. Voice↔Voice Round-Trip Benchmark
if ! run_benchmark "Voice↔Voice Round-Trip" "scripts/voice_roundtrip_benchmark.py"; then
    FAILED_BENCHMARKS+=("voice_roundtrip")
    OVERALL_STATUS="FAIL"
fi
echo ""

# 6. Stability Test
if ! run_benchmark "Stability Test" "scripts/stability_test.py"; then
    FAILED_BENCHMARKS+=("stability")
    OVERALL_STATUS="FAIL"
fi
echo ""

# Generate final report
echo "----------------------------------------"
echo "Generating Final Report"
echo "----------------------------------------"

python3 << 'EOF'
import json
import os
from datetime import datetime, timezone

report_dir = "reports"
benchmark_files = {
    "e2e_integration": "e2e_integration.md",
    "ttft": "ttft.json",
    "text_to_text": "text_to_text.md",
    "voice_to_text": "voice_to_text.md",
    "voice_roundtrip": "voice_roundtrip.md",
    "stability": "stability.md"
}

results = {}
for benchmark, filename in benchmark_files.items():
    filepath = os.path.join(report_dir, filename)
    if os.path.exists(filepath):
        if filename.endswith('.json'):
            with open(filepath, 'r') as f:
                results[benchmark] = json.load(f)
        else:
            results[benchmark] = {"file": filename, "exists": True}
    else:
        results[benchmark] = {"file": filename, "exists": False, "error": "File not found"}

# Generate final report
final_report = {
    "test_name": "Aziza Milestone 2 - Final Benchmark Report",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "overall_status": os.environ.get('OVERALL_STATUS', 'UNKNOWN'),
    "failed_benchmarks": os.environ.get('FAILED_BENCHMARKS', '').split(',') if os.environ.get('FAILED_BENCHMARKS') else [],
    "benchmark_results": results,
    "summary": {
        "total_benchmarks": len(benchmark_files),
        "passed_benchmarks": len([b for b, r in results.items() if r.get("exists", False) and r.get("status") == "PASS"]),
        "failed_benchmarks": len([b for b, r in results.items() if r.get("status") == "FAIL"]),
        "missing_benchmarks": len([b for b, r in results.items() if not r.get("exists", False)])
    }
}

# Save final report
with open(os.path.join(report_dir, "final_report.json"), 'w') as f:
    json.dump(final_report, f, indent=2)

# Generate Markdown report
with open(os.path.join(report_dir, "final_report.md"), 'w') as f:
    f.write("# Aziza Milestone 2 - Final Benchmark Report\n\n")
    f.write(f"**Timestamp:** {final_report['timestamp']}\n")
    f.write(f"**Overall Status:** {final_report['overall_status']}\n\n")
    f.write("## Summary\n\n")
    f.write(f"- **Total Benchmarks:** {final_report['summary']['total_benchmarks']}\n")
    f.write(f"- **Passed:** {final_report['summary']['passed_benchmarks']}\n")
    f.write(f"- **Failed:** {final_report['summary']['failed_benchmarks']}\n")
    f.write(f"- **Missing:** {final_report['summary']['missing_benchmarks']}\n\n")
    
    if final_report['failed_benchmarks']:
        f.write("## Failed Benchmarks\n\n")
        for benchmark in final_report['failed_benchmarks']:
            if benchmark:  # Skip empty strings
                f.write(f"- {benchmark}\n")
        f.write("\n")
    
    f.write("## Benchmark Results\n\n")
    for benchmark, result in results.items():
        f.write(f"### {benchmark.replace('_', ' ').title()}\n\n")
        if result.get("exists"):
            status = result.get("status", "UNKNOWN")
            f.write(f"**Status:** {status}\n")
            if "summary" in result:
                f.write("\n**Summary:**\n")
                for key, value in result["summary"].items():
                    f.write(f"- {key}: {value}\n")
        else:
            f.write("**Status:** MISSING\n")
        f.write("\n")
    
    f.write("## Recommendations\n\n")
    if final_report['overall_status'] == "PASS":
        f.write("✓ All benchmarks passed. Milestone 2 validation complete.\n")
    else:
        f.write("✗ Some benchmarks failed. Review individual benchmark reports for details.\n")
        f.write("\n**Next Steps:**\n")
        f.write("1. Review failed benchmark logs in telemetry/\n")
        f.write("2. Check system resources and service status\n")
        f.write("3. Verify adapter and Moshi worker integration\n")
        f.write("4. Re-run failed benchmarks after fixes\n")

print("Final report generated: reports/final_report.md")
EOF

OVERALL_STATUS="$OVERALL_STATUS"
FAILED_BENCHMARKS="${FAILED_BENCHMARKS[@]}"
export OVERALL_STATUS FAILED_BENCHMARKS

echo ""
echo "========================================"
echo "Benchmark Suite Complete"
echo "========================================"
echo "Overall Status: $OVERALL_STATUS"
echo ""
echo "Reports generated in: reports/"
echo "  - e2e_integration.md"
echo "  - ttft.json"
echo "  - ttft.csv"
echo "  - ttft.md"
echo "  - text_to_text.md"
echo "  - voice_to_text.md"
echo "  - voice_roundtrip.md"
echo "  - stability.md"
echo "  - final_report.md"
echo ""
echo "Telemetry logs in: telemetry/"
echo ""

# Exit with appropriate code
if [ "$OVERALL_STATUS" = "PASS" ]; then
    exit 0
else
    exit 1
fi
