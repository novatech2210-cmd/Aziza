import os
import subprocess
import json
import glob
from pathlib import Path
from datetime import datetime

base_dir = "/root/aziza-build"
baseline_dir = os.path.join(base_dir, "engineering/baseline")
os.makedirs(baseline_dir, exist_ok=True)

def write_md(filename, content):
    filepath = os.path.join(baseline_dir, filename)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Generated {filename}")

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        return f"Error executing {cmd}: {str(e)}"

# PART 1: REPOSITORY INVENTORY
print("Gathering repository inventory...")
tree_out = run_cmd(f"tree -L 3 {base_dir} | head -n 500")
write_md("REPOSITORY_INVENTORY.md", f"""# Repository Inventory
Date: {datetime.now().isoformat()}

## Directory Structure
```
{tree_out}
```

## Major Components
- **Backend:** `backend/`
- **Frontend:** `frontend/`
- **Training:** `training/`
- **Deployment:** `docker/`, `deployment/`
- **Configuration:** `configs/`
- **Benchmarks:** `benchmarks/`
- **Engineering Docs:** `engineering/`
""")

# PART 2: TECH STACK
print("Gathering tech stack...")
python_ver = run_cmd("python3 --version")
node_ver = run_cmd("node --version")
npm_ver = run_cmd("npm --version")
pm2_ver = run_cmd("pm2 --version")
docker_ver = run_cmd("docker --version")
os_info = run_cmd("cat /etc/os-release | grep PRETTY_NAME")
kernel_info = run_cmd("uname -r")
gpu_info = run_cmd("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
pip_deps = run_cmd("pip freeze | head -n 50")

write_md("TECH_STACK.md", f"""# Technology Stack Inventory

## Core Tools
- **Python:** {python_ver}
- **Node:** {node_ver}
- **NPM:** {npm_ver}
- **PM2:** {pm2_ver}
- **Docker:** {docker_ver}

## Infrastructure
- **OS:** {os_info}
- **Kernel:** {kernel_info}
- **GPU:** {gpu_info}

## Installed Python Packages (Sample)
```
{pip_deps}
```
""")

# PART 3: SERVICES
pm2_list = run_cmd("pm2 list")
docker_ps = run_cmd("docker ps")

write_md("SERVICES.md", f"""# Service Inventory

## PM2 Processes
```
{pm2_list}
```

## Docker Containers
```
{docker_ps}
```

## Network Ports (Listening)
```
{run_cmd("netstat -tuln | grep LISTEN | head -n 20")}
```
""")

# PART 4: ARCHITECTURE BASELINE
write_md("ARCHITECTURE_BASELINE.md", f"""# Architecture Baseline Snapshot

## System Overview
AZIZA is an AI assistant relying on Moshi for native Russian/Uzbek phonetic pronunciation, combined with low-latency Voice-to-Voice and Text-to-Text pipelines.

## Components
1. **Gateways:** WebSocket interfaces for streaming audio and text.
2. **Workers:** vLLM instances for text, Moshi for audio.
3. **Storage:** PersonaPlex DB for persona states, Redis for caching/sessions.

## Flow
User -> Cloudflare -> Nginx -> FastAPI Gateway -> PersonaPlex -> vLLM / Moshi Worker -> Response Pipeline.
""")

# PART 5: DEPENDENCY BASELINE
write_md("DEPENDENCY_BASELINE.md", f"""# Dependency Graph Baseline

## Top Level Dependencies
Based on `requirements.txt` and `package.json` (if present).
```
{run_cmd(f"cat {base_dir}/requirements.txt 2>/dev/null | head -n 30")}
```

## Potential Technical Debt in Dependencies
- Multiple duplicate package versions may exist.
- Review needed for unused imports via `flake8` or `vulture`.
""")

# PART 6: MODEL INVENTORY
models_ls = run_cmd(f"ls -lh {base_dir}/models/ 2>/dev/null")
cache_ls = run_cmd(f"ls -lh /root/.cache/huggingface/hub/ 2>/dev/null | head -n 20")
write_md("MODELS.md", f"""# Model Inventory

## Local Models Directory
```
{models_ls}
```

## HuggingFace Cache
```
{cache_ls}
```
""")

# PART 7: DATASET INVENTORY
datasets_ls = run_cmd(f"ls -lh {base_dir}/datasets/ 2>/dev/null")
write_md("DATASETS.md", f"""# Dataset Inventory

## Available Datasets
```
{datasets_ls}
```
""")

# PART 8: CONFIGURATION
write_md("CONFIGURATION.md", f"""# Configuration Inventory

## Config Files Found
```
{run_cmd(f"find {base_dir} -name '*.conf' -o -name '*.yaml' -o -name '*.yml' -o -name '.env*' | grep -v node_modules | head -n 50")}
```
""")

# PART 9: PERFORMANCE
mem_usage = run_cmd("free -h")
cpu_usage = run_cmd("top -bn1 | head -n 10")
gpu_usage = run_cmd("nvidia-smi")
write_md("PERFORMANCE_BASELINE.md", f"""# Performance Baseline

## Memory Usage
```
{mem_usage}
```

## CPU Usage
```
{cpu_usage}
```

## GPU Consumption
```
{gpu_usage}
```
""")

# PART 10: TEST BASELINE
pytest_out = run_cmd(f"cd {base_dir} && python3 -m pytest tests/ --maxfail=1 -v 2>&1 | tail -n 20")
write_md("TEST_BASELINE.md", f"""# Test Baseline

## Test Execution Summary (pytest)
```
{pytest_out}
```
""")

# PART 11: SECURITY BASELINE
write_md("SECURITY_BASELINE.md", f"""# Security Baseline

## Open Ports
```
{run_cmd("netstat -tuln | grep LISTEN")}
```

## Environment Files
```
{run_cmd(f"find {base_dir} -name '.env*' -type f | wc -l")} files found.
```
*Note: Secrets should not be committed to version control.*
""")

# PART 12: DEPLOYMENT BASELINE
write_md("DEPLOYMENT_BASELINE.md", f"""# Deployment Baseline

- **Server:** H100 Instance (83.126.40.53)
- **Processes:** Managed by PM2
- **Containers:** Docker used for supplementary services (Redis, MongoDB).
""")

# PART 13: DOCUMENTATION AUDIT
docs_ls = run_cmd(f"ls -l {base_dir}/engineering/ 2>/dev/null")
write_md("DOCUMENTATION_AUDIT.md", f"""# Documentation Audit

## Documents Found
```
{docs_ls}
```
""")

# PART 14: TECHNICAL DEBT
write_md("TECHNICAL_DEBT.md", f"""# Technical Debt Audit

## Unused Files / Broken Links
- To be thoroughly analyzed using AST tools.
- Several `.bak` or redundant log files observed in working directories.
""")

# PART 15: METRICS
py_loc = run_cmd(f"find {base_dir} -name '*.py' | xargs wc -l | tail -n 1")
js_loc = run_cmd(f"find {base_dir} -name '*.js' -o -name '*.jsx' | grep -v node_modules | xargs wc -l | tail -n 1")
write_md("METRICS.md", f"""# Baseline Metrics

## Lines of Code
- **Python:** {py_loc}
- **JS/TS:** {js_loc}
""")

# PART 16: ENGINEERING BASELINE
write_md("ENGINEERING_BASELINE.md", f"""# Engineering Snapshot

- **Current Epic:** VOICE_PLATFORM (VOICE-001)
- **Status:** Baseline recorded before commencing latency optimizations.
- **Governance:** Repository Guardian is active.
""")

# PART 17: MANIFEST
write_md("BASELINE_MANIFEST.md", f"""# Baseline Manifest
Created: {datetime.now().isoformat()}

## Index of Reports
1. [Repository Inventory](REPOSITORY_INVENTORY.md)
2. [Tech Stack](TECH_STACK.md)
3. [Services](SERVICES.md)
4. [Architecture Baseline](ARCHITECTURE_BASELINE.md)
5. [Dependency Graph](DEPENDENCY_BASELINE.md)
6. [Models](MODELS.md)
7. [Datasets](DATASETS.md)
8. [Configuration](CONFIGURATION.md)
9. [Performance](PERFORMANCE_BASELINE.md)
10. [Test Baseline](TEST_BASELINE.md)
11. [Security](SECURITY_BASELINE.md)
12. [Deployment](DEPLOYMENT_BASELINE.md)
13. [Documentation Audit](DOCUMENTATION_AUDIT.md)
14. [Technical Debt](TECHNICAL_DEBT.md)
15. [Metrics](METRICS.md)
16. [Engineering Snapshot](ENGINEERING_BASELINE.md)
""")

print("Baseline generation complete.")
