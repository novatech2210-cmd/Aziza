# Services Inventory

| Service | Purpose | Entry Point | Dependencies | Ports | Health Check | Startup Order |
|---|---|---|---|---|---|---|
| API Gateway | Routes traffic & WebSockets | `backend/services/api-gateway/dist/main.js` | Redis, Orchestrator | 8080 | `/health` | 5 |
| Orchestrator | Manages session and logic | `backend/services/orchestrator/main.py` | Redis | 8001 | `/health` | 4 |
| Moshi Worker | V2V and V2T Audio processing | `backend/services/moshi-worker/moshi_service.py` | Redis, Text API | 8020 | `/health` | 3 |
| PersonaPlex | Emotional state manager | `backend/persona-plex/main.py` | Redis, MongoDB | 8000 | `/docs` | 2 |
| vLLM English | English text inference | `vllm.entrypoints.openai.api_server` | None | 8002 | `/v1/models` | 1 |
| vLLM Uzbek | Uzbek text inference | `vllm.entrypoints.openai.api_server` | None | 8003 | `/v1/models` | 1 |
| Aziza Russian | Russian V2T & Text inference | `backend/gateway/serve_russian_test.py` | None | 8020 | `/docs` | 3 |
