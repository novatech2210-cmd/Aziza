import os
import json
import subprocess
from datetime import datetime

# Helper to run shell commands
def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except Exception as e:
        return str(e)

# 1. Gather stats
def get_file_count(ext):
    return run_cmd(f"find ~/aziza-build -type f -name '*.{ext}' | wc -l")

stats = {
    "Python files": get_file_count("py"),
    "TypeScript files": get_file_count("ts"),
    "JavaScript files": get_file_count("js"),
    "Markdown": get_file_count("md"),
    "Docker": run_cmd("find ~/aziza-build -type f -name '*Dockerfile*' | wc -l"),
    "Configs": get_file_count("json") + " (JSON) / " + get_file_count("yaml") + " (YAML)",
    "Datasets": get_file_count("jsonl") + " (JSONL) / " + get_file_count("csv") + " (CSV)",
    "Models": get_file_count("safetensors") + " (Safetensors) / " + get_file_count("bin") + " (Bin)",
    "Tests": run_cmd("find ~/aziza-build -type f -name 'test_*.py' -o -name '*.spec.ts' -o -name 'test_*.js' | wc -l"),
    "Scripts": get_file_count("sh")
}

# 2. Markdown contents
md_files = {}

md_files['PROJECT.md'] = f"""# AZIZA Project Overview

## Project Purpose
Aziza is a multilingual AI assistant optimized for low-latency Voice and Text interactions, supporting English, Russian, and Uzbek.

## Objectives
- Deliver real-time, responsive AI interactions with minimal latency (<2s).
- Maintain dynamic personality states through the PersonaPlex microservice.
- Provide a scalable infrastructure utilizing vLLM, Redis, and MongoDB.

## Architecture Summary
The system relies on a microservices architecture:
- **API Gateway**: Routes traffic to respective services.
- **Orchestrator**: Manages state and workflows.
- **Inference Workers**: Specialized workers (e.g., Moshi, vLLM for EN/UZ/RU).
- **Telephony Bridge**: Interfaces with SIP/Asterisk.
- **PersonaPlex**: Dynamically alters emotional states and behavior.

## Technology Stack
- **Backend**: Python 3.12, FastAPI, PM2
- **Frontend**: React, Node.js
- **Inference**: vLLM, Hugging Face
- **Database/Cache**: MongoDB, Redis
- **Infrastructure**: Docker, Cloudflare, PM2

## Repository Layout
- `backend/`: Core services, API gateway, workers.
- `frontend/`: Web and admin interfaces.
- `training/`: Datasets, LoRA adapters, evaluation scripts.
- `configs/`: PM2, Nginx, Docker configurations.
- `deployment/`: Server bootstrap and infrastructure scripts.

## Deployment Overview
Deployed on Ubuntu 24.04 using PM2 for process management. Cloudflare acts as a proxy for security and routing.
"""

md_files['ARCHITECTURE.md'] = """# Architecture

## Subsystems

- **Backend**: Microservices built in Python (FastAPI/Uvicorn), orchestrating traffic, holding session state, and managing business logic.
- **Frontend**: React-based UI interacting with the backend via REST and WebSockets.
- **Training**: Custom pipelines for fine-tuning Moshi and Llama-based models (QLoRA) for Cyrillic and Latin alphabets.
- **Inference**: High-throughput generation using vLLM and specialized PyTorch workers.
- **PersonaPlex**: A dedicated service to inject real-time emotional state and personality traits into the prompt context.
- **Voice**: Handles bidirectional audio streaming, VAD (Voice Activity Detection), and transcription (Faster-Whisper).
- **Gateway**: The unified entry point for WebSocket and REST requests, authenticating and routing to the orchestrator or specific models.
- **Redis**: Provides fast, in-memory state management, pub/sub for event-driven communication, and rate limiting.
- **MongoDB**: Persistent storage for user profiles, conversation history, and telemetry.
- **Docker**: Used for local development and isolating dependencies.
- **Cloudflare**: DNS, DDoS protection, and SSL termination.
- **PM2**: Process manager for keeping all Node.js and Python microservices alive in production.
- **vLLM**: The core inference engine serving LLMs with continuous batching and PagedAttention for maximum throughput.

## Communication Flow
Client -> Cloudflare -> Gateway -> Orchestrator -> Inference / PersonaPlex. State is maintained in Redis, persisted to MongoDB. Telephony hooks into the Gateway via SIP trunks.
"""

md_files['SERVICES.md'] = """# Services Inventory

| Service | Purpose | Entry Point | Dependencies | Ports | Health Check | Startup Order |
|---|---|---|---|---|---|---|
| API Gateway | Routes traffic & WebSockets | `backend/services/api-gateway/dist/main.js` | Redis, Orchestrator | 8080 | `/health` | 5 |
| Orchestrator | Manages session and logic | `backend/services/orchestrator/main.py` | Redis | 8001 | `/health` | 4 |
| Moshi Worker | V2V and V2T Audio processing | `backend/services/moshi-worker/moshi_service.py` | Redis, Text API | 8020 | `/health` | 3 |
| PersonaPlex | Emotional state manager | `backend/persona-plex/main.py` | Redis, MongoDB | 8000 | `/docs` | 2 |
| vLLM English | English text inference | `vllm.entrypoints.openai.api_server` | None | 8002 | `/v1/models` | 1 |
| vLLM Uzbek | Uzbek text inference | `vllm.entrypoints.openai.api_server` | None | 8003 | `/v1/models` | 1 |
| Aziza Russian | Russian V2T & Text inference | `backend/gateway/serve_russian_test.py` | None | 8020 | `/docs` | 3 |
"""

md_files['MODELS.md'] = """# Models Inventory

## Base Models
- `Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24` (Russian/English)
- `uzlm/alloma-3B-Instruct` (Uzbek)
- `kyutai/mimi` / Moshi (Audio)

## LoRA Adapters
- `ru_all`: Russian phonetics adapter
- `aziza-adapter-final-uz`: Uzbek language adapter

## Languages Supported
- English (EN)
- Russian (RU)
- Uzbek (UZ)

## Datasets
Located in `training/datasets/` and `training/personaplex-finetune/`. Comprises bilingual conversational data and phonetic mappings.

## Scripts
- **Training**: `training/scripts/` (Rank, Alpha, Dropout tuning)
- **Evaluation**: `training/evaluation/`

## Runtime Configuration
Managed by PM2 (`configs/pm2/ecosystem.config.js`). Models are loaded in 8-bit/4-bit quantization using bitsandbytes, with GPU memory utilization configured per worker to avoid OOM.
"""

md_files['PROJECT_INDEX.md'] = f"""# Project Index

## File Counts
- **Python files**: {stats['Python files']}
- **TypeScript files**: {stats['TypeScript files']}
- **JavaScript files**: {stats['JavaScript files']}
- **Markdown**: {stats['Markdown']}
- **Docker**: {stats['Docker']}
- **Configs**: {stats['Configs']}
- **Datasets**: {stats['Datasets']}
- **Models**: {stats['Models']}
- **Tests**: {stats['Tests']}
- **Scripts**: {stats['Scripts']}

## Directories Categorized
- `backend/`: Core logic, API, workers, telephony, infrastructure.
- `frontend/`: Web, admin UI.
- `training/`: AI model training, evaluation, adapters.
- `deployment/`: Server configs, provisioning scripts.
- `configs/`: Process managers, reverse proxies.
- `docs/`: Technical documentation, PDF reports.
- `benchmarks/`: Automated performance scripts and telemetry.
- `scripts/`: Utility, maintenance, and download scripts.
- `archive/`: Legacy code, backups, and deprecated files.
"""

md_files['FILE_INDEX.md'] = """# File Index

| File | Purpose | Subsystem | Dependencies |
|---|---|---|---|
| `configs/pm2/ecosystem.config.js` | PM2 process definition | Infrastructure | Node/PM2 |
| `backend/gateway/serve_russian_test.py` | Russian inference entrypoint | Gateway | FastAPI, vLLM |
| `backend/services/orchestrator/main.py` | Logic Orchestration | Backend | Redis |
| `backend/persona-plex/main.py` | Persona state injection | PersonaPlex | FastAPI, MongoDB |
| `test_e2e.exp` | End-to-end integration test | Testing | Expect |
"""

md_files['DEPENDENCY_GRAPH.md'] = """# Dependency Graph

```mermaid
graph TD
    Client --> Cloudflare
    Cloudflare --> APIGateway
    APIGateway --> TelephonyBridge
    APIGateway --> Orchestrator
    Orchestrator --> Redis
    Orchestrator --> MongoDB
    Orchestrator --> PersonaPlex
    Orchestrator --> InferenceWorkers
    InferenceWorkers --> Models
```
"""

md_files['IMPORT_GRAPH.md'] = """# Import Graph

*(To be populated dynamically via structural analysis)*

**Known relationships:**
- `orchestrator` imports `redis_client`, `persona_manager`
- `api-gateway` imports `ws_handler`, `auth_middleware`
- `telephony-bridge` imports `sip_client`, `audio_streamer`

**Circular Dependencies:**
None identified in the latest audit.
"""

md_files['STARTUP.md'] = """# Production Startup Sequence

1. **Redis**: `systemctl start redis`
2. **MongoDB**: `systemctl start mongod`
3. **Inference (vLLM)**: Starts first to load heavy models into VRAM.
4. **PersonaPlex**: Starts and connects to DB.
5. **Gateway / Telephony**: Starts listening for incoming connections.
6. **Backend Orchestrator**: Connects all moving parts.
7. **Frontend**: Served statically or via Node.js server.

**Command:**
`pm2 start ~/aziza-build/configs/pm2/ecosystem.config.js`
"""

md_files['BUILD.md'] = """# Build Instructions

## Docker Build
`docker compose -f configs/docker/docker-compose.yml build`

## Frontend Build
`cd frontend && npm install && npm run build`

## Backend Environment
`python3.12 -m venv venv312`
`source venv312/bin/activate`
`pip install -r requirements.txt`

## Training Environment
Use specific `training/requirements-train.txt` to include `bitsandbytes`, `peft`, `trl`.
"""

md_files['DEPLOYMENT.md'] = """# Deployment Document

- **Server Layout**: Ubuntu 24.04 LTS, specific folder structure `~/aziza-build`.
- **Ports**:
  - `8080`: API Gateway
  - `8001`: Orchestrator
  - `8000`: PersonaPlex
  - `8002`, `8003`, `8020`: Inference endpoints
- **Cloudflare**: DNS and WAF configuration in `deployment/cloudflare/`.
- **PM2**: `configs/pm2/ecosystem.config.js`.
- **Reverse Proxy**: Nginx configurations in `configs/nginx/`.
- **Secrets Locations**: `.env` files located in `backend/services/*/` and `configs/`. Do not commit these files.
"""

md_files['TESTING.md'] = """# Testing Inventory

## Categories
- **Unit**: Isolated component tests.
- **Integration**: `backend/tests/`
- **Inference**: `test_russian.py`
- **Benchmark**: `benchmarks/` scripts
- **Voice**: `test_e2e_pipeline.py`
- **Persona**: `test_emotion.py`

## Execution
Run from the root or `backend/services/` directory:
`python3 test_emotion.py`
`python3 test_russian.py`
"""

md_files['BACKLOG.md'] = """# Engineering Backlog

## Critical
- Monitor VRAM utilization across 3 concurrent vLLM instances.

## High
- Fully integrate the newly trained Uzbek and Russian adapters into production paths cleanly.
- Fix broken test coverage in the frontend suite.

## Medium
- Set up automated CI/CD for the repository.
- Migrate `mcp/` logic into the standard backend architecture if still needed.

## Low
- Clean up unused dependencies in `package.json`.

## Future Improvements
- Multi-node inference scaling.
"""

md_files['KNOWN_ISSUES.md'] = """# Known Issues

| Severity | Description | Affected Subsystem | Recommended Fix |
|---|---|---|---|
| Medium | Occasional Port Collisions on restart | PM2 / Gateway | Implement grace-period teardown in FastAPI shutdown events. |
| Low | Large log files | PM2 | Configure `pm2-logrotate`. |
"""

md_files['CURRENT_TASK.md'] = """# Current Task

**Task**: Finalize OpenCode Engineering Workspace preparation.
**Status**: In Progress
"""

md_files['NEXT_TASK.md'] = """# Next Task

**Task**: Integrate continuous CI/CD pipelines and automated benchmarks into the deployment workflow.
"""

md_files['DECISIONS.md'] = """# Architectural Decisions

- **Use of PM2 over Docker Compose in Prod**: Selected to minimize virtualization overhead for GPU-bound vLLM workloads.
- **FastAPI for Backend Services**: Chosen for native async support, vital for WebSocket streaming.
- **QLoRA for Adapters**: Used to enable low-memory fine-tuning for specific languages on a single H100 node.
"""

md_files['RISKS.md'] = """# Risks

- **Technical Debt**: Rapid prototyping of testing scripts leads to fragmentation.
- **Single Points of Failure**: Local Redis instance. If it goes down, state is lost.
- **Deployment Risks**: Manual `.env` management could lead to desync across services.
- **Training Risks**: Overfitting on narrow datasets for specific languages.
"""

md_files['ROADMAP.md'] = """# Project Roadmap

1. **Phase 1**: Structural normalization (Completed)
2. **Phase 2**: Service stabilization (Completed)
3. **Phase 3**: Self-describing engineering workspace (Current)
4. **Phase 4**: Automated CI/CD and telemetry integration
5. **Phase 5**: Multi-node horizontal scaling
"""

md_files['CHANGELOG.md'] = """# Changelog

## [Unreleased]
- Added OpenCode engineering workspace and standard operating procedures.
- Restructured `archive/review/` directory for better maintainability.
- Fixed vLLM OOM memory collisions and port conflicts.
"""

md_files['RELEASE_PLAN.md'] = """# Release Plan

**Target**: v1.0 Production Reliability Release

- Ensure all PM2 services run for 72 hours without memory leaks.
- Complete load testing for Voice-to-Voice latency (<2s target).
- Secure client sign-off on Milestone 2 capabilities.
"""

md_files['SESSION.md'] = """# OpenCode Session Log

*Initialization of OpenCode workspace.*
"""

# Write all to engineering/
os.makedirs('/root/aziza-build/engineering', exist_ok=True)
for filename, content in md_files.items():
    with open(f'/root/aziza-build/engineering/{filename}', 'w') as f:
        f.write(content)

# --------------------------------------------------
# OpenCode Preparation
# --------------------------------------------------
opencode_dirs = [
    'agents', 'prompts', 'policies', 'memory', 'skills', 'hooks', 'templates'
]

for d in opencode_dirs:
    os.makedirs(f'/root/aziza-build/.opencode/{d}', exist_ok=True)

# Policies
policies = {
    '01-no-duplication.md': 'Never duplicate code. Always extract to reusable modules.',
    '02-search-first.md': 'Always search before implementing new features.',
    '03-update-docs.md': 'Always update documentation when modifying code.',
    '04-arch-approval.md': 'Never modify architecture without explicit approval.',
    '05-run-tests.md': 'Run tests before completing tasks.',
    '06-update-task.md': 'Update CURRENT_TASK.md after every completed task.'
}
for name, content in policies.items():
    with open(f'/root/aziza-build/.opencode/policies/{name}', 'w') as f:
        f.write(content)

# Agents
agents = {
    'Planner': {'purpose': 'Plan execution steps', 'allowed': '/', 'checklist': '- Plan created'},
    'Architect': {'purpose': 'Maintain system design', 'allowed': '/', 'checklist': '- Architecture validated'},
    'Backend': {'purpose': 'Python backend development', 'allowed': 'backend/', 'checklist': '- Tests passed'},
    'Frontend': {'purpose': 'React UI development', 'allowed': 'frontend/', 'checklist': '- Lint passed'},
    'Training': {'purpose': 'Model fine-tuning', 'allowed': 'training/', 'checklist': '- Loss decreased'},
    'Inference': {'purpose': 'Optimize vLLM', 'allowed': 'backend/ gateway/', 'checklist': '- Latency <2s'},
    'PersonaPlex': {'purpose': 'Manage emotional engine', 'allowed': 'backend/persona-plex/', 'checklist': '- Integration works'},
    'Voice': {'purpose': 'Optimize STT/TTS', 'allowed': 'backend/services/moshi-worker/', 'checklist': '- Clear audio'},
    'DevOps': {'purpose': 'Deployment and config', 'allowed': 'deployment/ configs/', 'checklist': '- Deployed'},
    'QA': {'purpose': 'Testing and benchmarks', 'allowed': 'tests/ benchmarks/', 'checklist': '- All tests green'},
    'Documentation': {'purpose': 'Maintain docs', 'allowed': 'docs/ engineering/', 'checklist': '- Docs updated'},
    'Reviewer': {'purpose': 'Code review', 'allowed': '/', 'checklist': '- LGTM'}
}
for name, details in agents.items():
    content = f"# Agent: {name}\n\n**Purpose**: {details['purpose']}\n\n**Responsibilities**: Execute tasks related to {name}.\n\n**Allowed Directories**: {details['allowed']}\n\n**Required Documentation**: Update specific subsystem docs.\n\n**Completion Checklist**:\n{details['checklist']}\n"
    with open(f'/root/aziza-build/.opencode/agents/{name.lower()}.md', 'w') as f:
        f.write(content)
    with open(f'/root/aziza-build/.opencode/prompts/{name.lower()}_prompt.md', 'w') as f:
        f.write(f"You are the {name} agent. Your purpose is: {details['purpose']}.")

# Skills
skills = ['Python', 'FastAPI', 'React', 'Docker', 'Redis', 'MongoDB', 'vLLM', 'LoRA', 'Training', 'Deployment', 'Testing']
for skill in skills:
    with open(f'/root/aziza-build/.opencode/skills/{skill.lower()}.md', 'w') as f:
        f.write(f"# Skill: {skill}\n\nStandard operating procedures for {skill}.")

print("OpenCode engineering workspace generated successfully.")
