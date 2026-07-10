AZIZA BUILD STATUS AUDIT — Where Are We Right Now?
You are performing a technical audit of the Aziza AI Platform build. The target final product is a multilingual, full-duplex voice AI assistant (named Aziza) supporting Russian, Uzbek Latin, and Uzbek Cyrillic, running on a Vast.ai H100 instance managed by PM2 + systemd. The full spec is defined in the AZIZA_MASTER_BUILD_PROMPT.
Go through each item below and answer with one of: ✅ Done | ⚠️ Partial (explain what works and what doesn't) | ❌ Not started | 🔍 Unknown (needs checking).
For every item that is not ✅ Done, state exactly what the next concrete action is to complete it.

PHASE 2 — UZBEK LANGUAGE

audit_tokenizer.py — Has it been run against Vikhr-Llama-3.1-8B-Instruct? Did Uzbek Latin special chars (Oʻ oʻ Gʻ gʻ) and Uzbek Cyrillic (Ҳ ҷ Қ Ғ Ў) achieve ≥90% single-token coverage? Was tokenizer extension needed and applied?
aziza-uzbek.jsonl — Does it exist? How many lines? Does validate_uzbek_dataset.py exit 0? Are Latin and Cyrillic dialogues separated (no mixing)?
train_uzbek.py — Does it exist? Does --dry_run pass? Is the locked config (r=16, alpha=32, NF4, lr=2e-4, batch=4, grad_accum=4, epochs=3) intact?
Uzbek QLoRA training run — Has it been executed? Did it complete all 3 stages without OOM or NaN loss? Does adapter_model.safetensors exist at /root/aziza/adapters/uz_colloquial/? Is aziza-adapter-final-uz.tar.gz archived off-GPU?
eval_uzbek.py — Does it exist? Has it been run? Did it pass all 5 gates (script fidelity ≥80%, language switching ≥95%, no English regression)? Does eval_uzbek_report.txt exist in the adapter directory?
bench_ttft.py — Does it exist? Has it been run across all 3 language modes? Is p95 TTFT <100ms for Russian, Uzbek Latin, and Uzbek Cyrillic? Does bench_ttft_report.txt exist?
serve_multilingual.py — Does it exist (extended from serve_russian_test.py)? Does it accept --language arg and load the correct adapter? Is it running on port 8020?
NestJS API Gateway language routing — Are uz-latin and uz-cyrillic added as first-class session language modes? Is the Uzbek drift guard (>10% ASCII → retry) implemented? Does /health report all 3 adapter statuses?
PersonaPlex — Are Uzbek Latin and Uzbek Cyrillic system prompt contexts added (with correct formal "Siz" register for Latin)?


PHASE 3 — PRODUCTION INFRASTRUCTURE

Orchestrator GPU pool routing — Is POST /session returning {ws_url} pointing directly to an idle Moshi worker? Is Redis worker registry working (idle → busy → idle transitions)? Does it return 503 cleanly when all workers are busy?
Vue 3 Voice Frontend — Does the <VoiceChat> AudioWorklet component exist? Does browser mic → PCM → WebSocket → Moshi → audio playback work end-to-end with <300ms latency? Is the language selector (RU / UZ-Latin / UZ-Cyrillic) wired to session init?
Asterisk ARI Bridge (asterisk_ari_bridge.py) — Does it exist? Does it connect to Asterisk ARI on port 8088? Does an incoming SIP call trigger StasisStart, bridge to Moshi, and return audio? Is the full-duplex (simultaneous send/receive) path working?
ecosystem.config.js — Does it exist and define all 6+ processes (gateway, orchestrator, workers, ari-bridge, personaplex, frontend)? Does pm2 start ecosystem.config.js bring everything up with 0 restarts in 60s? Has pm2 save + pm2 startup been tested across a server reboot?
Git repository (aziza-platform) — Does it exist as a private repo? Are all existing assets committed to the dev branch? Is main branch protection enabled? Does .gitignore exclude *.safetensors, *.tar.gz, *.jsonl?


FINAL ACCEPTANCE CHECKLIST — Go through each line:

Russian QLoRA eval ≥80% Cyrillic accuracy → evidence file?
Uzbek Latin QLoRA eval ≥80% accuracy → evidence file?
Uzbek Cyrillic QLoRA eval ≥80% accuracy → evidence file?
TTFT p95 <100ms for all 3 language modes → evidence file?
Text→Text response <3s in all 3 modes → tested?
Voice→Text transcript <2s after end-of-speech (RU + UZ) → tested?
Voice↔Voice browser round-trip <300ms (RU + UZ) → tested?
Voice↔Voice phone SIP call working end-to-end (RU + UZ) → tested?
PersonaPlex in-character 5+ turns in Uzbek → tested?
10-minute continuous session, no crash or memory leak → tested?
All adapter .tar.gz backups stored off-GPU → confirmed?


After answering every item above, provide:

A summary table: Item | Status | Blocker / Next Action
The critical path to production — what is the single next thing that must happen before anything else can proceed?
An honest time estimate to full production readiness given the current state, assuming the H100 is available tonight.
