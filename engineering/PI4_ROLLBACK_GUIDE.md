# PI-4 Rollback Guide

## Rollback Triggers

Execute rollback immediately if any of the following occur:
- WER > 20% on Uzbek test set
- RU/EN regression detected (any test failure)
- PersonaPlex emotion score drops below 22/22
- GPU crashes or OOM during inference
- LiveKit integration failures
- Crash loop (> 3 restarts in 10 min)

## Rollback Procedure

### Step 1: Stop moshi-worker

```bash
pm2 stop moshi-worker
```

### Step 2: Remove Uzbek adapter

Edit `/root/aziza-build/backend/services/moshi-worker/moshi_engine.py`:

Comment out or remove the Uzbek adapter loading block:
```python
# uz_adapter_path = "/root/aziza-build/training/lora/adapters/moshi_uz_v1/final"
# if os.path.exists(uz_adapter_path):
#     self.moshi_lm.load_adapter(uz_adapter_path, adapter_name="uz")
```

### Step 3: Restart moshi-worker

```bash
pm2 start moshi-worker
```

### Step 4: Verify base model mode

```bash
curl http://localhost:8001/health
# Should show: "mode": "Architecture Separation (Base Moshi Model only)"
```

### Step 5: Delete adapter artifacts

```bash
rm -rf /root/aziza-build/training/lora/adapters/moshi_uz_v1
```

### Step 6: Notify team

Report rollback reason and timeline for re-attempt.

## Partial Rollback

If only specific sessions are affected, use adapter switching instead of full rollback:

```python
# In moshi_engine.py _switch_to_session:
self.moshi_lm.set_adapter("multilingual")  # Fall back to multilingual
```

## Recovery

After root cause is fixed:
1. Re-run training from last checkpoint
2. Re-validate with smoke test
3. Re-deploy following `PI4_DEPLOYMENT_GUIDE.md`
