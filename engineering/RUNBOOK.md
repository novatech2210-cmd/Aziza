# AZIZA Production Operations Runbook

## Quick Reference

| Service | Port | Health Check | PM2 Name |
|---------|------|-------------|----------|
| API Gateway | 8080 | `curl localhost:8080/health` | api-gateway |
| Orchestrator | 8001 | `curl localhost:8001/health` | orchestrator |
| PersonaPlex | 8000 | `curl localhost:8000/health` | personaplex |
| vLLM English | 8002 | `curl localhost:8002/health` | vllm-english |
| vLLM Uzbek | 8003 | `curl localhost:8003/health` | vllm-uzbek |
| Redis | 6379 | `redis-cli ping` | external |
| MongoDB | 27017 | `mongosh --eval 'db.runCommand("ping")'` | external |

## Start All Services

```bash
pm2 start ~/aziza-build/configs/pm2/ecosystem.config.js
```

**Start order**: Redis → MongoDB → vLLM English → vLLM Uzbek → PersonaPlex → Orchestrator → API Gateway

## Stop All Services

```bash
pm2 stop all
```

## Restart a Service

```bash
pm2 restart <service-name>
# Example: pm2 restart moshi-worker
```

## View Logs

```bash
# Real-time logs
pm2 logs <service-name>

# Recent logs (last 100 lines)
pm2 logs <service-name> --lines 100

# Error logs only
pm2 logs <service-name> --err

# All service logs
pm2 logs
```

## Check Service Status

```bash
pm2 status
```

## Health Checks

### Automated Health Check
```bash
python3 ~/aziza-build/deployment/validate_env.py
```

### Manual Health Checks
```bash
# API Gateway
curl -s http://localhost:8080/health

# Orchestrator
curl -s http://localhost:8001/health

# PersonaPlex
curl -s http://localhost:8000/health

# vLLM English
curl -s http://localhost:8002/health

# vLLM Uzbek
curl -s http://localhost:8003/health

# Redis
redis-cli ping

# MongoDB
mongosh --eval 'db.runCommand("ping")'
```

## GPU Monitoring

```bash
# Real-time GPU stats
nvidia-smi

# Detailed VRAM usage
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv

# Watch mode
watch -n 2 nvidia-smi
```

## Common Issues and Fixes

### 1. Service Won't Start

**Symptom**: PM2 shows `errored` status

**Diagnosis**:
```bash
pm2 logs <service-name> --lines 50
pm2 status
```

**Fixes**:
- **Port already in use**: `lsof -i :<port>` → kill conflicting process
- **Missing environment variables**: Check `.env` files in service directories
- **Out of memory**: Check `free -h` and `nvidia-smi` for VRAM
- **Python path issues**: Ensure `PYTHONPATH` includes `/root/aziza-build/backend:/root/aziza-build/backend/services`

### 2. vLLM Out of Memory

**Symptom**: vLLM service crashes or restarts repeatedly

**Diagnosis**:
```bash
nvidia-smi
pm2 logs vllm-english --err --lines 50
```

**Fixes**:
- Reduce `--gpu-memory-utilization` in ecosystem.config.js
- Check for other GPU processes: `fuser -v /dev/nvidia*`
- Kill unused GPU processes
- Reduce `--max-num-seqs` to lower concurrent requests

### 3. Redis Connection Refused

**Symptom**: Services can't connect to Redis

**Diagnosis**:
```bash
redis-cli ping
systemctl status redis
```

**Fixes**:
- Start Redis: `systemctl start redis`
- Check Redis config: `redis-cli config get *`
- Check memory: `redis-cli info memory`

### 4. MongoDB Connection Issues

**Symptom**: PersonaPlex or API Gateway can't save data

**Diagnosis**:
```bash
mongosh --eval 'db.runCommand("ping")'
mongosh --eval 'db.adminCommand({listDatabases:1})'
```

**Fixes**:
- Start MongoDB: `systemctl start mongod`
- Check disk space: `df -h`
- Check MongoDB logs: `journalctl -u mongod --since "1 hour ago"`

### 5. High Latency (TTFT > 2s)

**Symptom**: Slow first-token response

**Diagnosis**:
```bash
# Check GPU utilization
nvidia-smi

# Check active sessions
curl -s http://localhost:8080/api/admin/metrics | jq .

# Check vLLM status
curl -s http://localhost:8002/health
```

**Fixes**:
- Reduce concurrent sessions
- Check for GPU thermal throttling
- Restart vLLM if model loading is stale
- Check Redis for session queue backlog

### 6. WebSocket Connection Failures

**Symptom**: Frontend can't connect to voice/chat

**Diagnosis**:
```bash
# Check API Gateway logs
pm2 logs api-gateway --lines 50

# Check if port is listening
ss -tlnp | grep 8080
```

**Fixes**:
- Restart API Gateway: `pm2 restart api-gateway`
- Check JWT_SECRET is set
- Check CORS configuration
- Verify WebSocket upgrade headers

### 7. Disk Space Full

**Symptom**: Services crash, can't write logs

**Diagnosis**:
```bash
df -h
du -sh /root/aziza-build/logs/*
```

**Fixes**:
```bash
# Run log cleanup
python3 ~/aziza-build/deployment/cleanup_logs.py --max-age-days 14 --compress

# Emergency cleanup
find /root/aziza-build/logs -name "*.log.*" -mtime +7 -delete
```

### 8. Memory Leak

**Symptom**: Service memory grows over time

**Diagnosis**:
```bash
pm2 monit
# Check specific process memory
ps aux | grep <service-name>
```

**Fixes**:
- PM2 will auto-restart if `max_memory_restart` is hit
- Check for Redis key growth: `redis-cli dbsize`
- Check MongoDB collection sizes
- Restart the specific service

## Log Rotation

pm2-logrotate is configured:
- **Max file size**: 50MB
- **Retention**: 30 rotated files
- **Compression**: enabled
- **Rotation schedule**: daily at midnight

```bash
# Check pm2-logrotate status
pm2 conf

# Manual rotation
pm2 flush  # Clear all logs
```

## Backup Procedures

### Database Backup
```bash
# MongoDB backup
mongodump --db aziza --out /root/aziza-build/backups/mongo-$(date +%Y%m%d)

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /root/aziza-build/backups/redis-$(date +%Y%m%d).rdb
```

### Configuration Backup
```bash
# PM2 process list
pm2 save

# Git commit
cd ~/aziza-build && git add -A && git commit -m "Backup: $(date)"
```

## Deployment

### Standard Deployment
```bash
cd ~/aziza-build
git pull origin main
cd backend/services/api-gateway && npm run build
pm2 restart api-gateway
```

### Full Deployment
```bash
bash ~/aziza-build/deployment/deploy.sh
```

### Rollback
```bash
bash ~/aziza-build/deployment/rollback.sh
```

## Monitoring Dashboard

Access the admin dashboard at `http://localhost:8080/api/admin` with admin credentials.

### Key Metrics to Watch
- **TTFT P95**: Should be < 2000ms
- **Error Rate**: Should be < 5%
- **GPU Utilization**: Normal range 30-80%
- **GPU Temperature**: Should be < 85°C
- **Active Sessions**: Should be < MAX_CONCURRENT_SESSIONS
- **Memory Usage**: Watch for steady growth (leak indicator)

### Alert Rules (Epic 9)
| Alert | Threshold | Action |
|-------|-----------|--------|
| Error Rate > 10% | Critical | Check service logs, restart if needed |
| P95 TTFT > 3s | Warning | Check GPU load, reduce sessions |
| Success Rate < 90% | Critical | Investigate failing requests |
| GPU Temp > 85°C | Critical | Check cooling, reduce load |
| GPU Memory > 95% | Warning | Kill other GPU processes |
| Request Rate > 100/min | Info | Monitor for sustained load |

## Emergency Procedures

### Total System Reset
```bash
# Stop everything
pm2 stop all

# Clear Redis
redis-cli FLUSHALL

# Restart in order
pm2 start ~/aziza-build/configs/pm2/ecosystem.config.js
```

### Nuclear Option (Full Restart)
```bash
pm2 kill
redis-cli FLUSHALL
systemctl restart mongod
pm2 start ~/aziza-build/configs/pm2/ecosystem.config.js
```

## Contact

- **Repository**: /root/aziza-build
- **Logs**: /root/aziza-build/logs/
- **Config**: /root/aziza-build/configs/pm2/ecosystem.config.js
- **Deploy Script**: /root/aziza-build/deployment/deploy.sh
