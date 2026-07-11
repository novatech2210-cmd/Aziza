# AGENTS.md

## What This Is

AZIZA — multilingual AI voice assistant (Russian, Uzbek, English) built on fine-tuned Moshi/PersonaPlex 7B models. Microservices architecture: FastAPI + NestJS gateway + vLLM inference + Redis + MongoDB, deployed on GPU instances via PM2.

## Read First

`.opencode/project/BOOTSTRAP.md` mandates reading before every session. The key files:

- `engineering/PROJECT.md` — system overview
- `engineering/ARCHITECTURE.md` — immutable architecture (frozen, no changes without approval)
- `engineering/DEVELOPMENT_CHARTER.md` — mandatory rules
- `engineering/CURRENT_TASK.md` — active work authorization

## Key Commands

### Start all services
```bash
pm2 start ~/aziza-build/configs/pm2/ecosystem.config.js
```

### Start order matters (Redis → MongoDB → vLLM → PersonaPlex → Gateway → Orchestrator → Frontend)

### Frontend
```bash
cd frontend && npm install && npm run build   # build
cd frontend && npm run dev                     # dev server (proxies to :8080)
cd frontend && npm test                        # unit tests (vitest)
```

### Backend API Gateway (NestJS, port 8080)
```bash
cd backend/services/api-gateway && npm run build && npm run start:prod
cd backend/services/api-gateway && npm test    # unit tests (jest, 50 tests)
```

### Python services (orchestrator, moshi-worker, persona-plex)
All run under `venv312`:
```bash
source /root/aziza-build/venv312/bin/activate
```

### Python tests
```bash
cd backend && python3 -m pytest tests/ -q      # integration tests (7 tests)
```

### Training (requires GPU, use screen/tmux)
```bash
source /root/personaplex-env/bin/activate   # or venv312 for newer scripts
python3 training/scripts/train_russian.py --help
```

## Service Ports

| Port | Service |
|------|---------|
| 8080 | API Gateway (NestJS) |
| 8001 | Orchestrator |
| 8000 | PersonaPlex (FastAPI) |
| 8002 | vLLM English inference |
| 8003 | vLLM Uzbek inference |
| 8020 | Russian test server |

## Architecture Constraints

- **Architecture is frozen.** No new databases, frameworks, or languages without human approval.
- Low latency requirement: first-token < 2s for voice pipelines.
- `PYTHONPATH` must include `/root/aziza-build/backend:/root/aziza-build/backend/services` for orchestrator.
- vLLM services use `CUDA_VISIBLE_DEVICES` and specific `--gpu-memory-utilization` — don't change without checking VRAM budget.

## Environment & Secrets

- `.env` files in `backend/services/*/`, `backend/persona-plex/`, `deployment/` — **never commit these.**
- `HF_TOKEN` required for gated model downloads (HuggingFace).
- `REDIS_URL` defaults to `redis://localhost:6379`.
- `MONGO_URL` defaults to `mongodb://localhost:27017/aziza`.
- `JWT_SECRET` — required for API gateway auth. WS gateways + passport both enforce HS256.
- `CORS_ORIGINS` — comma-separated allowed origins for CORS (default: `http://localhost:5173,http://localhost:3000`).

## Security

- Helmet middleware provides security headers (X-Content-Type-Options, X-Frame-Options, etc.).
- Global ValidationPipe enforces DTO validation with whitelist + forbidNonWhitelisted.
- Auth endpoints rate-limited: login 5/min, register 3/min.
- Admin WebSocket requires JWT with `role=admin`.
- DOMPurify sanitizes all markdown HTML output (XSS prevention).
- User chat messages stripped of HTML tags + limited to 4096 chars.

## Testing

```bash
cd frontend && npm test                        # 13 frontend tests (vitest)
cd backend/services/api-gateway && npm test    # 50 NestJS tests (jest)
cd backend && python3 -m pytest tests/ -q      # 7 Python tests (pytest)
```

Integration tests: `backend/tests/`
Benchmarks: `benchmarks/`

## Code Conventions

- Python 3.12 in `venv312`
- NestJS (TypeScript) for the API Gateway
- Vue 3 + Vite + Tailwind CSS 4 for frontend
- PM2 for process management — always update `configs/pm2/ecosystem.config.js` for service changes
- One task at a time, one branch per task (charter rule)
- Always search before implementing; never duplicate functionality
- Update `engineering/` docs when making architectural changes

## Common Gotchas

- `vllm-english` and `vllm-uzbek` share GPU (`CUDA_VISIBLE_DEVICES: "0"`) — don't run both with high `gpu-memory-utilization` simultaneously.
- Training uses ~35-45 GB VRAM; inference uses ~20 GB. Check `nvidia-smi` before starting.
- `cloudflared tunnel` URLs are ephemeral — new URL each restart.
- PM2 config has hardcoded env vars including `HF_TOKEN` — be aware when updating.
- The `training/personaplex-finetune/` directory has its own `AGENTS.md` — read it for finetuning-specific guidance.
