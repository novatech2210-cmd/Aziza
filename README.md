# Aziza Russian Cyrillic Test Scripts
**Novatech | AZIZA-RUSSIAN-TEST-PLAN | 03 June 2026**

Text-in / text-out Russian Cyrillic test pipeline for PersonaPlex-7B + QLoRA adapter.
No voice/audio/TTS/ASR required for this test.

---

## Files

| File | Purpose |
|---|---|
| `train_russian.py` | QLoRA fine-tuning — run tonight in screen/tmux |
| `eval_russian.py` | Acceptance gate suite — run after training completes |
| `serve_russian_test.py` | FastAPI test server on port 8020 |

---

## Prerequisites

```bash
pip install transformers peft trl bitsandbytes datasets accelerate \
            fastapi uvicorn pydantic torch sentencepiece
```

VRAM required: 35–45 GB during training, ~20 GB during serving.

---

## Step 0 — Fix blocker first

```bash
source /root/personaplex-env/bin/activate
pip install "huggingface-hub>=1.5.0" "transformers>=4.40.0" --force-reinstall
pip check
python3 -c "from huggingface_hub import login; print('OK')"
pm2 restart aziza-moshi-worker && pm2 status
```

Expected: aziza-moshi-worker online, restarts count frozen.

---

## Step 1 — Train (tonight, ~12–18 hrs)

```bash
# Check VRAM is clear first
nvidia-smi

# Start persistent session
screen -S aziza-train
# or: tmux new -s aziza-train

cd /workspace/aziza-web/fine-tuning
source /root/personaplex-env/bin/activate

cp train_russian.py eval_russian.py serve_russian_test.py .

export HF_TOKEN=hf_your_token_here

# Dry run to validate dataset first (no GPU needed)
python3 train_russian.py --register colloquial \
    --dataset_path data/aziza-bilingual/aziza-bilingual.jsonl \
    --output_base /root/aziza/adapters \
    --dry_run

# If dry run passes, start TensorBoard then training
tensorboard --logdir runs --host 0.0.0.0 --port 6006 &
python3 train_russian.py --register colloquial \
    --dataset_path data/aziza-bilingual/aziza-bilingual.jsonl \
    --output_base /root/aziza/adapters

# Detach: Ctrl+A D (screen) or Ctrl+B D (tmux)
```

### OOM fallback
```bash
python3 train_russian.py --register colloquial \
    --dataset_path data/aziza-bilingual/aziza-bilingual.jsonl \
    --output_base /root/aziza/adapters \
    --batch_size 2 --grad_accum 8
```

### Fast fallback (4–6 hrs, lower quality)
```bash
python3 train_russian.py --register colloquial \
    --dataset_path data/aziza-bilingual/aziza-bilingual.jsonl \
    --output_base /root/aziza/adapters \
    --max_seq_len 256 --epochs 1
```

Monitor:
```bash
watch -n 10 nvidia-smi
tail -f runs/ru_colloquial_*/trainer_log.jsonl
```

---

## Step 2 — Evaluate (tomorrow morning, ~15 min)

```bash
export HF_TOKEN=hf_your_token_here
python3 eval_russian.py \
    --adapter /root/aziza/adapters/ru_colloquial \
    --ttft_target_ms 180
```

All gates must pass. Results saved to `/root/aziza/adapters/ru_colloquial/eval_results.json`.

Exit 0 = all pass. Exit 1 = fix needed.

**If pass_rate < 80%:** rerun training with `--register all` to use all Russian data.

---

## Step 3 — Deploy (tomorrow midday)

```bash
export HF_TOKEN=hf_your_token_here
export MODEL_ID=nvidia/personaplex-7b-v1
export ADAPTER_PATH=/root/aziza/adapters/ru_colloquial
export PORT=8020

# Start via PM2
pm2 start "uvicorn serve_russian_test:app --host 0.0.0.0 --port 8020 --workers 1" \
    --name aziza-russian-test --interpreter none
pm2 save
pm2 logs aziza-russian-test
```

Add port 8020 in Vast.ai console → instance → Edit → Open Ports.

### Cloudflare tunnel (new tunnel for this test)
```bash
cloudflared tunnel --url http://localhost:8020
# Note the URL printed — send this to Ivan
```

---

## Step 4 — Smoke test before Ivan connects

```bash
TUNNEL=https://your-tunnel.trycloudflare.com

# 1. Health check
curl $TUNNEL/health

# 2. Automated readiness check — must return ready_for_demo: true
curl $TUNNEL/test/cyrillic

# 3. Manual chat test
curl -X POST $TUNNEL/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Привет! Как тебя зовут?", "temperature": 0.7}'
```

---

## What Ivan sends (client test protocol)

```
POST https://{tunnel-url}/chat
Content-Type: application/json

{"message": "Ваш русский текст здесь", "temperature": 0.7}
```

Response:
```json
{
  "response": "Ответ на русском языке...",
  "has_cyrillic": true,
  "cyrillic_ratio": 0.85,
  "input_tokens": 12,
  "output_tokens": 45,
  "total_ms": 1240.5,
  "adapter": "ru_colloquial"
}
```

Pass criteria: `has_cyrillic: true`, `total_ms < 3000`, coherent Russian.

---

## Fallback — base model (no adapter)

If adapter is not ready in time:
```bash
export ADAPTER_PATH=""   # empty = base model only
pm2 restart aziza-russian-test
```

Tell Ivan: "Base model only — fine-tuned adapter Day+1."

---

## What is skipped for this test

- VibeVoice / TTS / ASR
- Asterisk ARI telephony
- Uzbek adapters
- ru_academic / ru_professional adapters

All deferred, not cancelled.
