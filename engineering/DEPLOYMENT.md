# Deployment Document

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
