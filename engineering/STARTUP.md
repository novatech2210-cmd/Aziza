# Production Startup Sequence

1. **Redis**: `systemctl start redis`
2. **MongoDB**: `systemctl start mongod`
3. **Inference (vLLM)**: Starts first to load heavy models into VRAM.
4. **PersonaPlex**: Starts and connects to DB.
5. **Gateway / Telephony**: Starts listening for incoming connections.
6. **Backend Orchestrator**: Connects all moving parts.
7. **Frontend**: Served statically or via Node.js server.

**Command:**
`pm2 start ~/aziza-build/configs/pm2/ecosystem.config.js`
