# File Index

| File | Purpose | Subsystem | Dependencies |
|---|---|---|---|
| `configs/pm2/ecosystem.config.js` | PM2 process definition | Infrastructure | Node/PM2 |
| `backend/gateway/serve_russian_test.py` | Russian inference entrypoint | Gateway | FastAPI, vLLM |
| `backend/services/orchestrator/main.py` | Logic Orchestration | Backend | Redis |
| `backend/persona-plex/main.py` | Persona state injection | PersonaPlex | FastAPI, MongoDB |
| `test_e2e.exp` | End-to-end integration test | Testing | Expect |
