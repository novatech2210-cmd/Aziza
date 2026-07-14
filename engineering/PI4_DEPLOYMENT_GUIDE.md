# PI-4 Production Deployment Guide

## Pre-Deployment Checklist

- [ ] Training completed with validation loss < training loss
- [ ] Adapter saved to `/root/aziza-build/training/lora/adapters/moshi_uz_v1/final/`
- [ ] Voice certification passed (WER < 15%, CER < 5%)
- [ ] Persona evaluation passed (22/22 emotion tests)
- [ ] No regression in RU/EN tests
- [ ] LiveKit integration tested
- [ ] Stress testing passed (30min + 60min sessions)
- [ ] PM2 config reviewed

## Deployment Steps

### 1. Stop moshi-worker

```bash
pm2 stop moshi-worker
```

### 2. Update moshi_engine.py

Edit `/root/aziza-build/backend/services/moshi-worker/moshi_engine.py`:

```python
# Add Uzbek adapter path
uz_adapter_path = "/root/aziza-build/training/lora/adapters/moshi_uz_v1/final"
if os.path.exists(uz_adapter_path):
    logger.info(f"Loading UZ adapter from {uz_adapter_path}...")
    self.moshi_lm.load_adapter(uz_adapter_path, adapter_name="uz")
```

### 3. Restart moshi-worker

```bash
pm2 start moshi-worker
```

### 4. Verify health

```bash
pm2 logs moshi-worker --lines 20
curl http://localhost:8001/health
```

### 5. Run voice certification

```bash
# Uzbek voice test
python3 benchmarks/benchmark_uzbek_voice.py

# PersonaPlex certification
python3 -m pytest backend/tests/ -q
```

## Post-Deployment Monitoring

| Metric | Alert Threshold |
|--------|-----------------|
| GPU utilization | > 95% for > 5 min |
| VRAM usage | > 45GB |
| Moshi latency (p99) | > 3s |
| Adapter load failures | Any |
| Crash loop | > 3 restarts in 10 min |

## Rollback

See `PI4_ROLLBACK_GUIDE.md`.
