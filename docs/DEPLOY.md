## Architecture Overview

```
                    CloudFlare Tunnel
Browser ──────────► (random-url.trycloudflare.com) ──────────► VPS :8010
                                                                  │
                                                          ┌───────┴───────┐
                                                          │   server.py   │
                                                          │   (FastAPI)   │
                                                          │   port 8010   │
                                                          └───────┬───────┘
                                                                  │
                                          ┌───────────────────────┼───────────────────────┐
                                          │                       │                       │
                                   ┌──────┴──────┐       ┌───────┴───────┐       ┌───────┴───────┐
                                   │  PostgreSQL  │       │   vLLM EN/RU  │       │   vLLM UZ     │
                                   │  port 5432   │       │   GPU-0 :8000 │       │   GPU-1 :8001 │
                                   └─────────────┘       └───────────────┘       └───────────────┘
```

**Single command** runs everything: `python server.py`

---

## Prerequisites

- Ubuntu 22.04+ VPS with NVIDIA GPUs (tested on Vast.ai dual-GPU instances)
- Python 3.10+
- Node.js 18+ and npm (for frontend build)
- PostgreSQL 14+
- NVIDIA drivers + CUDA 12.x
- At least 16GB VRAM total (8GB per GPU for 3B models)

---

## 1. VPS Setup

### Install system packages
```bash
apt update && apt install -y postgresql postgresql-contrib curl
```

### Start PostgreSQL
```bash
pg_ctlcluster 16 main start    # or: systemctl start postgresql
```

### Create database and user
```bash
sudo -u postgres psql <<EOF
CREATE USER aziza WITH PASSWORD 'aziza_password';
CREATE DATABASE aziza_db OWNER aziza;
GRANT ALL PRIVILEGES ON DATABASE aziza_db TO aziza;
EOF
```

> **Note:** `server.py` auto-creates all tables on first run. No manual schema setup needed.

---

## 2. Backend Setup

### Clone and navigate
```bash
cd /workspace
# Copy aziza-web/backend/ to VPS
cd /workspace/backend
```

### Install Python dependencies
```bash
pip install -r requirements.txt
pip install rank-bm25
```

> If `faiss-gpu` fails, try `pip install faiss-gpu-cu12` or `pip install faiss-cpu` as fallback.

### Verify dependencies
```bash
python3 -c "import faiss; print('FAISS OK')"
python3 -c "from sentence_transformers import SentenceTransformer; print('SentenceTransformers OK')"
python3 -c "from rank_bm25 import BM25Okapi; print('BM25 OK')"
python3 -c "import vllm; print('vLLM OK')"
```

---

## 3. Configuration

All settings are in `config.py` and overridable via environment variables.

### Key environment variables

```bash
# Server
export PORT=8010
export HOST=0.0.0.0

# Database
export DATABASE_URL="postgresql://aziza:aziza_password@localhost:5432/aziza_db"

# JWT (CHANGE THIS in production!)
export JWT_SECRET="your-secure-random-secret-here"

# LLM endpoints (auto-launched by server.py)
export LLM_URL_EN="http://localhost:8000"
export LLM_URL_UZ="http://localhost:8001"
export LLM_MODEL_EN="Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
export LLM_MODEL_UZ="uzlm/alloma-3B-Instruct"

# vLLM settings
export LAUNCH_VLLM=true          # set false to manage vLLM separately
export VLLM_GPU_MEMORY_UTIL=0.6  # VRAM allocation per model
export VLLM_MAX_NUM_SEQS=4       # concurrent sequences (lower = less GPU spikes)
export VLLM_MAX_MODEL_LEN=4096
export LLM_GPU_EN=0              # GPU index for EN/RU model
export LLM_GPU_UZ=1              # GPU index for UZ model

# RAG
export RAG_ENABLED=true
export RAG_DEVICE=cpu             # cpu recommended (GPU VRAM used by vLLM)
export RAG_INDEX_PATH="./rag_index"

# CORS (comma-separated origins, or * for all)
export CORS_ORIGINS="*"
```

---

## 4. Start the Server

```bash
cd /workspace/backend
python server.py
```


1. Launches vLLM on GPU-0 (Vikhr) and GPU-1 (Alloma)
2. Waits for both LLM servers to become healthy
3. Starts PostgreSQL and initializes tables
4. Loads RAG embedding model (multilingual-e5-base)
5. Starts FastAPI on port 8010

### Expected startup logs
```
[VLLM] Launching EN/RU — Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24 on GPU 0, port 8000...
[VLLM] Launching UZ — uzlm/alloma-3B-Instruct on GPU 1, port 8001...
[VLLM] EN/RU — Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24 ready in 45.2s
[VLLM] UZ — uzlm/alloma-3B-Instruct ready in 48.1s
[DB] PostgreSQL is already running.
[DB] Connection pool ready.
[DB] Schema initialized.
[RAG] Loading embedding model: intfloat/multilingual-e5-base (device=cpu)
[RAG] Embedder ready.
[RAG] New empty index created (hybrid mode).
[SERVER] AZIZA backend started on port 8010
```

### Verify the server is running
```bash
curl http://localhost:8010/docs          # FastAPI Swagger UI
curl http://localhost:8000/v1/models     # vLLM EN/RU
curl http://localhost:8001/v1/models     # vLLM UZ
```

---

## 5. Expose via CloudFlare Tunnel

```bash
# Install cloudflared (one-time)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Start tunnel (only ONE tunnel needed — everything is on port 8010)
cloudflared tunnel --url http://localhost:8010 &
```

CloudFlare will output a URL like:
```
https://random-words-here.trycloudflare.com
```

Copy this URL — you'll need it for the frontend `.env`.

---

## 6. Frontend Setup

### Build locally (on your dev machine)

```bash
cd aziza-web/frontend
```

### Configure the `.env` file
```bash
# Replace with your actual CloudFlare tunnel URL
VITE_AUTH_API_URL=https://your-tunnel-url.trycloudflare.com
VITE_CHAT_API_URL=https://your-tunnel-url.trycloudflare.com
VITE_CHAT_WS_URL=wss://your-tunnel-url.trycloudflare.com
VITE_ADMIN_API_URL=https://your-tunnel-url.trycloudflare.com
VITE_ADMIN_WS_URL=wss://your-tunnel-url.trycloudflare.com

VITE_DEV_SKIP_AUTH=false
```

### Install and build
```bash
npm install
npm run build
```

This generates the `dist/` folder with production-ready static files.

### Serve the frontend

**Option A — Dev server (for testing):**
```bash
npm run dev
# Opens at http://localhost:5173
```

**Option B — Deploy static files (production):**

Upload `dist/` to any static hosting:
- Vercel: `npx vercel --prod`
- Netlify: drag & drop `dist/` folder
- GitHub Pages
- Any web server (nginx, Apache)

**Option C — Serve from VPS with nginx:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /workspace/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 7. First Login

1. Open the frontend in your browser
2. Click **Register** — the **first user** automatically becomes **admin**
3. Subsequent registrations create regular users
4. Admin can access the Admin Panel from the user menu dropdown

---

## 8. API Endpoints Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Create account |
| POST | `/login` | Get JWT tokens |
| POST | `/refresh` | Refresh access token |
| GET | `/me` | Current user info |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/ws/chat/{session_id}` | WebSocket chat (token in query param) |
| GET | `/chat-history` | List saved sessions |
| POST | `/chat-history` | Save session |
| DELETE | `/chat-history/{session_id}` | Delete session |

### Tiers & Usage
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tiers` | All available tiers |
| GET | `/me/tier` | Current user's tier |
| PUT | `/me/tier` | Change tier |
| GET | `/me/usage` | Usage stats |

### Admin (requires admin role)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/sessions` | Active sessions |
| DELETE | `/admin/sessions` | Disconnect all |
| DELETE | `/admin/sessions/{id}` | Terminate one |
| GET | `/admin/gpu` | GPU stats |
| GET | `/admin/gpu/history` | GPU history (60s) |
| GET | `/admin/latency/heatmap` | Latency heatmap |
| GET | `/admin/errors` | Error log |
| GET | `/admin/logs` | Filtered logs |
| GET | `/admin/rag/stats` | RAG index stats |
| POST | `/admin/rag/ingest` | Ingest documents |
| POST | `/admin/rag/search` | Search RAG |
| GET | `/admin/rag/documents` | List documents |
| DELETE | `/admin/rag/clear` | Clear RAG index |
| WS | `/admin/ws/stats` | Live admin stats |

---

## 9. Running as a Background Service

### Using screen (simple)
```bash
screen -S aziza
cd /workspace/backend
python server.py
# Press Ctrl+A, then D to detach
# screen -r aziza to reattach
```

### Using systemd (production)
```ini
# /etc/systemd/system/aziza.service
[Unit]
Description=AZIZA AI Assistant Backend
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/workspace/backend
Environment=JWT_SECRET=your-secure-secret
Environment=LAUNCH_VLLM=true
Environment=RAG_ENABLED=true
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable aziza
systemctl start aziza
systemctl status aziza     # check status
journalctl -u aziza -f     # view logs
```

---

## 10. Troubleshooting

### "All connection attempts failed" in chat
The backend can't reach vLLM. Check:
```bash
curl http://localhost:8000/v1/models
curl http://localhost:8001/v1/models
```
If not responding, vLLM may still be loading or crashed. Check logs.

### WebSocket disconnects after idle
CloudFlare tunnels drop idle connections after ~100s. The server sends ping every 30s to prevent this. If still happening, check CloudFlare tunnel logs.

### RAG not returning results
Verify the embedding model loaded:
```bash
curl -X POST http://localhost:8010/admin/rag/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'
```

### Database connection error
```bash
pg_isready                                    # check if PostgreSQL is running
pg_ctlcluster 16 main start                   # start if not running
sudo -u postgres psql -c "\\l"                # list databases
```

### GPU out of memory
Reduce vLLM memory allocation:
```bash
export VLLM_GPU_MEMORY_UTIL=0.5   # default is 0.6
```

---

## 11. File Structure

```
aziza-web/
├── backend/
│   ├── server.py              # Single entry point — runs everything
│   ├── config.py              # All settings (env-var overridable)
│   ├── database.py            # PostgreSQL pool + schema
│   ├── auth.py                # JWT tokens + password hashing
│   ├── routes/
│   │   ├── auth_routes.py     # Login, register, refresh
│   │   ├── chat_routes.py     # WebSocket chat + history
│   │   ├── admin_routes.py    # Admin dashboard endpoints
│   │   └── tier_routes.py     # Tier + usage endpoints
│   ├── services/
│   │   ├── gpu.py             # NVIDIA GPU monitoring
│   │   ├── llm.py             # LLM routing (EN/RU/UZ)
│   │   ├── metrics.py         # Latency/error/session tracking
│   │   ├── rag.py             # RAG engine (FAISS + BM25 hybrid)
│   │   └── vllm_launcher.py   # Auto-launch vLLM subprocesses
│   ├── requirements.txt
│   └── rag_index/             # Created at runtime (FAISS + metadata)
├── frontend/
│   ├── src/
│   │   ├── views/             # LoginView, ChatView, AdminView, UsageView
│   │   ├── components/        # Chat, admin, toast components
│   │   ├── stores/            # Pinia stores (auth, chat, theme)
│   │   └── router/            # Vue Router config
│   ├── dist/                  # Production build output
│   ├── .env                   # API URLs (set before building)
│   └── package.json
└── DEPLOY.md                  # This file
```
