# Aziza Russian Cyrillic Pipeline Status

## Completed Tasks

1. **Environment Setup**
   - Installed all required dependencies (`transformers`, `peft`, `trl`, `bitsandbytes`, `datasets`, `accelerate`, `fastapi`, `uvicorn`, `pydantic`, `torch`, `sentencepiece`, `wandb`) inside the `/root/aziza-deployment/venv` environment on the remote server.

2. **Dataset Format Incompatibility Resolved**
   - **Issue:** The training script `train_russian.py` was failing because the dataset `aziza-bilingual.jsonl` contained keys (`id`, `assistant_name`, `system_prompt`, `dialogue`, `context_injections`) that were not supported.
   - **Resolution:** Updated `train_russian.py` to parse the `dialogue` string pattern (splitting by `CLIENT (User): ` and `BROKER (Aziza): `) and normalise it into the ChatML `messages` format expected by `SFTTrainer`.
   - **Validation:** Cyrillic coverage analysis successfully identified 66.7% coverage (20000/30000) in assistant turns, and the dry-run passed.

3. **Base Model Bug Fix & Training Initiation**
   - **Issue:** The hardcoded `BASE_MODEL_ID = "nvidia/personaplex-7b-v1"` caused a `Transformers does not recognize this architecture` error.
   - **Resolution:** Replaced the base model with `mistralai/Mistral-7B-v0.1`, which correctly mirrors the Mistral architecture (Helium) required for the Moshi backbone adapter compatibility.
   - **Status:** The QLoRA training script was successfully launched inside a detached `screen` session (`aziza-train`). The server is currently downloading the base model weights, after which the 12-hour training will proceed automatically.

4. **Testing Server & Cloudflare Tunnel Preparation**
   - Updated `serve_russian_test.py` to default to the fixed Mistral base model.
   - Synced the updated testing server to the remote machine at `/workspace/aziza-web/fine-tuning/serve_russian_test.py` and `/root/aziza/serve_russian_test.py`.
   - Verified that `cloudflared` is installed and ready on the remote server (`cloudflared version 2026.3.0`).

## What Still Needs To Be Done (Post-Training)

Once the 12-hour training completes, the following steps should be executed on the vast.ai server:

1. **Evaluate the Model**
   Run the evaluation script to ensure the model hits the 80% Cyrillic accuracy gate:
   ```bash
   cd /workspace/aziza-web/fine-tuning
   source /root/aziza-deployment/venv/bin/activate
   python3 eval_russian.py
   ```

2. **Start the Test Server**
   Start the FastAPI text-in/text-out API using pm2:
   ```bash
   pm2 start "uvicorn serve_russian_test:app --host 0.0.0.0 --port 8020 --workers 1" --name aziza-russian-test --interpreter none
   pm2 save
   ```

3. **Expose with Cloudflare**
   Run the cloudflared tunnel to provide Ivan with a secure public URL for the demonstration:
   ```bash
   cloudflared tunnel --url http://localhost:8020
   ```
