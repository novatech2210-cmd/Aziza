**AZIZA AI PLATFORM**

**MASTER PRODUCTION BUILD PROMPT**

Novatech · Client: Ivan · Confidential

+:-------------------:+:-------------------:+:-------------------:+
| **TARGET            | **INTERACTION       | **INFRASTRUCTURE**  |
| LANGUAGES**         | MODES**             |                     |
|                     |                     | **Vast.ai H100 SXM  |
| **Russian (RU) +    | **Text → Text**     | 80GB**              |
| Uzbek (UZ)**        |                     |                     |
|                     | **Voice → Text**    | PM2 + systemd (no   |
| Latin & Cyrillic    |                     | Docker)             |
| scripts             | **Voice ↔ Voice     |                     |
|                     | (Full Duplex)**     | Asterisk ARI +      |
|                     |                     | Moshi               |
+---------------------+---------------------+---------------------+

> **1. COMPLETE STACK OVERVIEW**

**1.1 Architecture Decision Record**

  -----------------------------------------------------------------
  **LOCKED:** All architecture decisions below are final and
  approved. Do not introduce Docker, do not change inference
  engine, do not change model family without team sign-off.

  -----------------------------------------------------------------

  --------------- ------------------------ ----------------------------
  **Layer**       **Technology**           **Decision Rationale**

  Base Model      Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24   Strong multilingual
                                           Cyrillic + Latin coverage.
                                           7B fits H100 with NF4 quant
                                           leaving room for LoRA.

  Fine-Tuning     QLoRA r=16 alpha=32 NF4  LOCKED CONFIG --- do not
                                           change. Proven on Russian.
                                           Uzbek uses identical
                                           pipeline.

  Voice Inference Moshi (full-duplex)      Only production-ready
                                           full-duplex voice model. No
                                           VAD latency. Native
                                           streaming.

  Text Inference  vLLM (text-only path)    Used for text→text mode
                                           only. Moshi handles voice
                                           paths.

  API Gateway     NestJS (port 3000)       WebSocket session
                                           management, auth, Redis
                                           pub/sub, language routing.

  Middleware      FastAPI (port 8020)      Inference bridge:
                                           text-in/text-out and PCM
                                           audio frames to Moshi.

  Persona Engine  PersonaPlex              Dynamic system prompt
                  (microservice)           injection. Personality NOT
                                           baked into weights.

  Telephony       Asterisk ARI + FFmpeg    SIP trunk → RTP → PCM →
                                           WebSocket → Moshi. FFmpeg
                                           for codec transcoding.

  Session Store   Redis (pub/sub + state)  Worker registration, session
                                           state, max_sessions=1 per
                                           GPU worker enforced.

  Process Mgmt    PM2 + systemd            No Docker. All processes
                                           native on H100 instance. PM2
                                           ecosystem.config.js.

  Frontend        Vue 3 + Pinia            Text chat UI + voice UI.
                                           Cloudflare tunnel on port
                                           8010 for Ivan demo access.

  Telephony DB    PostgreSQL               User auth, session history,
                                           usage tracking, tier
                                           management.
  --------------- ------------------------ ----------------------------

**1.2 Three Interaction Modes --- How They Work**

  -------------- ---------------------------------------------------
  **Mode**       **Data Flow**

  Text → Text    Browser POST /chat → NestJS Gateway → FastAPI
                 (serve_test.py) → Vikhr-Llama-3.1+QLoRA adapter → JSON
                 response → Browser

  Voice → Text   Browser mic (WebAudio API) → 16kHz PCM → WebSocket
                 → Moshi ASR → text transcript → NestJS → LLM → text
                 response → Browser

  Voice ↔ Voice  Browser mic → PCM frames → WebSocket → Moshi
                 full-duplex inference → PCM audio frames → Browser
                 speaker (AudioWorklet) --- simultaneously
                 bidirectional. Phone: SIP → Asterisk → ARI → FFmpeg
                 → PCM → same Moshi path.
  -------------- ---------------------------------------------------

**1.3 Language Routing**

Every session carries a language tag: ru \| uz-latin \| uz-cyrillic. The
NestJS Gateway uses this tag to: (1) select the correct QLoRA adapter,
(2) inject the correct PersonaPlex system prompt, (3) apply the language
drift guard (retry if \>10% ASCII in response). The Moshi worker loads
the adapter at session init. Language switching mid-session is not
supported --- a new session must be created.

> **2. CURRENT STATUS --- WHAT IS DONE VS PENDING**

  -------------------------- ------------- ------------- --------------------
  **Component**              **Russian**   **Uzbek**     **Notes**

  Tokenizer audit script     ✅ N/A        **⚡ NEXT**   audit_tokenizer.py
                                                         ready to run

  Dataset (JSONL, ChatML     ✅ Done       ❌ Pending    HuggingFace sources
  format)                                                identified

  train\_\*.py script        ✅ Done       ❌ Not        Clone of
                                           written       train_russian.py

  QLoRA training run         ✅ Done       ❌ Not        \~12-18hrs on H100
  (3-stage)                                started       

  Adapter eval (\>80%        ✅ Passed     ❌ Not run    eval_uzbek.py not
  accuracy)                                              written

  Adapter archived (.tar.gz) ✅ Done       ❌ Not done   

  serve\_\*\_test.py (port   ✅ Running    ❌ Not built  Extend existing
  8020)                                                  serve script

  PersonaPlex system prompts ✅ Done       ❌ Not added  uz-latin +
                                                         uz-cyrillic contexts

  API Gateway language       ✅ Done       ❌ Not added  Add uz-latin /
  routing                                                uz-cyrillic modes

  TTFT benchmark (\<100ms    ✅ Passing    ❌ Not        bench_ttft.py not
  p95)                                     benchmarked   written

  Voice→Text (Moshi ASR      ⚠️ Partial    ⚠️ Partial    Moshi worker runs,
  path)                                                  no ASR endpoint
                                                         wired to frontend

  Full-duplex Voice↔Voice    ⚠️ Partial    ⚠️ Partial    Moshi tested
  (Moshi)                                                standalone; not
                                                         wired into NestJS

  Vue 3 frontend (text chat) ✅ Built      ✅ Built      Based on
                                                         aziza-web/frontend

  Vue 3 frontend (voice UI)  ❌ Not built  ❌ Not built  AudioWorklet + mic
                                                         input needed

  Orchestrator GPU pool      ❌ Not done   ❌ Not done   TASK-3.1 in Phase 3
  routing                                                

  Asterisk ARI bridge        ❌ Not built  ❌ Not built  TASK-3.2 ---
                                                         critical path

  PM2 ecosystem.config.js    ❌ Not        ❌ Not        TASK-3.3
                             written       written       

  Git repository + branch    ❌ Not        ❌ Not        TASK-3.4
  strategy                   created       created       

  End-to-end SIP call test   ❌ Not done   ❌ Not done   TASK-3.5 --- final
                                                         gate
  -------------------------- ------------- ------------- --------------------

> **3. PHASE 2 --- UZBEK LANGUAGE COMPLETION**

  ------------------------------------------------- ----------------
  **PHASE 2 Multilingual Fine-Tuning**              **Russian ✅ \|
                                                       Uzbek ⏳**

  ------------------------------------------------- ----------------

**3.1 Dataset Strategy --- No Waiting for Ivan**

Uzbek datasets are available NOW on HuggingFace. Do not wait. Pull,
process, and train immediately. Ivan\'s custom dataset (if delivered)
can be merged as a second fine-tuning pass later.

  ---------------------------------- ---------- ---------------- -------------------------
  **Dataset**                        **Size**   **Script**       **Use**

  behbudiy/alpaca-cleaned-uz         52,000     Uzbek Latin      PRIMARY ---
                                     pairs                       instruction/response,
                                                                 Alpaca format, Google
                                                                 Translate quality

  saillab/alpaca-uzbek-cleaned       52,000     Uzbek Latin      SECONDARY --- second
                                     pairs                       independent translation,
                                                                 adds variation

  behbudiy/translation-instruction   20,000     Latin            Professional/formal
                                     pairs                       register. EN↔UZ
                                                                 bilingual. Higher quality
                                                                 filter.

  tahrirchi/uz-books                 \~40,000   Latin+Cyrillic   CYRILLIC SOURCE --- prose
                                     books                       corpus. Convert to
                                                                 dialogue pairs for
                                                                 Cyrillic training.

  Den4ikAI/russian_dialogues         2.47M rows Cyrillic         Russian supplement if
                                                                 aziza-bilingual.jsonl
                                                                 needs augmentation.
  ---------------------------------- ---------- ---------------- -------------------------

+-----------------------------------------+:--------------------------------:+
| **TASK-2.1 Tokenizer Audit --- Uzbek    | **⚡ START HERE**                |
| Character Coverage**                    |                                  |
|                                         | Owner: Chris / H100              |
+-----------------------------------------+----------------------------------+
| **Objective:** Run audit_tokenizer.py against Vikhr-Llama-3.1-8B-Instruct tokenizer. |
| Verify ≥90% single-token coverage for all Uzbek Latin special graphemes    |
| and Uzbek Cyrillic characters. Decide whether tokenizer extension is       |
| needed before any training begins.                                         |
|                                                                            |
| > **•** Characters to audit --- Uzbek Latin: Oʻ oʻ Gʻ gʻ Sh sh Ch ch Ng ng |
| >                                                                          |
| > **•** Characters to audit --- Uzbek Cyrillic: Ҳ ҳ Ҷ ҷ Қ қ Ғ ғ Ў ў        |
| >                                                                          |
| > **•** For each char: print token IDs, decoded tokens, fragment count.    |
| > Flag any \>2 tokens.                                                     |
| >                                                                          |
| > **•** If any Latin char fragments to \>3 tokens: add via                 |
| > tokenizer.add_tokens() and resize embeddings.                            |
| >                                                                          |
| > **•** Save extended tokenizer to /adapters/tokenizer-uz-extended/ if     |
| > extension applied.                                                       |
| >                                                                          |
| > **•** Run 50-sentence Uzbek Latin corpus through tokenizer. Compute      |
| > coverage ratio.                                                          |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** Script produces coverage report to stdout with PASS/FAIL verdict   |
| >                                                                          |
| > **✓** Coverage ≥90% on Uzbek Latin confirmed                             |
| >                                                                          |
| > **✓** Cyrillic chars verified (Vikhr-Llama has existing Cyrillic coverage from |
| > Russian training)                                                        |
| >                                                                          |
| > **✓** If extension applied: adapter_config.json reflects new vocab_size  |
+----------------------------------------------------------------------------+

+-----------------------------------------------------+:---------------------------------------------------:+
| **TASK-2.2 Dataset Preparation --- Uzbek Latin +    | **PENDING**                                         |
| Cyrillic**                                          |                                                     |
|                                                     | Owner: Chris / H100                                 |
+-----------------------------------------------------+-----------------------------------------------------+
| **Depends on:** TASK-2.1 (tokenizer coverage confirmed first)                                             |
+-----------------------------------------------------------------------------------------------------------+
| **Objective:** Download, sample, and format Uzbek datasets into aziza-uzbek.jsonl. Target: ≥3,000         |
| validated dialogue pairs (1,500 Latin + 1,500 Cyrillic). Must match exact ChatML messages format used by  |
| train_russian.py.                                                                                         |
|                                                                                                           |
| > **•** Run: from datasets import load_dataset; ds = load_dataset(\"behbudiy/alpaca-cleaned-uz\")         |
| >                                                                                                         |
| > **•** Sample 1,200 pairs for academic+professional register (Latin). Sample 300 colloquial pairs from   |
| > saillab source.                                                                                         |
| >                                                                                                         |
| > **•** For Cyrillic: use tahrirchi/uz-books --- extract paragraph pairs and reformat as dialogue turns.  |
| >                                                                                                         |
| > **•** Normalise ALL records to: {\"messages\": \[{\"role\":\"system\",\"content\":\"\<Aziza persona in  |
| > Uzbek\>\"},{\"role\":\"user\",\"content\":\"\...\"},{\"role\":\"assistant\",\"content\":\"\...\"}\]}    |
| >                                                                                                         |
| > **•** System turn must contain Uzbek Aziza persona: \"Siz --- Aziza, ovozli AI-assistentsiz\...\"       |
| > (formal uz-latin) or Cyrillic equivalent.                                                               |
| >                                                                                                         |
| > **•** Write validate_uzbek_dataset.py: check valid JSON, required keys, no English drift (\>10% ASCII = |
| > fail), script purity per line.                                                                          |
| >                                                                                                         |
| > **•** CRITICAL: No Latin/Cyrillic mixing within a single dialogue. Each dialogue is mono-script.        |
+-----------------------------------------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                                                   |
|                                                                                                           |
| > **✓** ≥3,000 validated lines in aziza-uzbek.jsonl                                                       |
| >                                                                                                         |
| > **✓** validate_uzbek_dataset.py exits 0 with: total lines, Latin count, Cyrillic count, failed=0        |
| >                                                                                                         |
| > **✓** Dataset backed up to aziza-uzbek.jsonl.tar.gz                                                     |
+-----------------------------------------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-2.3 Write train_uzbek.py**       | **PENDING**                      |
|                                         |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-2.1 → TASK-2.2                                        |
+----------------------------------------------------------------------------+
| **Objective:** Clone train_russian.py into train_uzbek.py. Change only     |
| dataset path, language arg default, and adapter output name. If tokenizer  |
| was extended in TASK-2.1, load from /adapters/tokenizer-uz-extended/       |
| instead of HuggingFace.                                                    |
|                                                                            |
| > **•** Copy train_russian.py → train_uzbek.py                             |
| >                                                                          |
| > **•** Change BASE_MODEL_ID default language to uz_latin                  |
| >                                                                          |
| > **•** Change default ADAPTER output to                                   |
| > /root/aziza/adapters/uz_colloquial                                       |
| >                                                                          |
| > **•** If tokenizer extended: add \--tokenizer_path arg, load             |
| > AutoTokenizer.from_pretrained(args.tokenizer_path)                       |
| >                                                                          |
| > **•** LOCKED CONFIG unchanged: r=16, alpha=32, NF4, lr=2e-4, batch=4,    |
| > grad_accum=4, max_seq=512, epochs=3                                      |
| >                                                                          |
| > **•** Add checkpoint saves after Stage 1 → uz-stage1/ and Stage 2 →      |
| > uz-stage2/                                                               |
| >                                                                          |
| > **•** Dry run first: python3 train_uzbek.py \--dry_run to validate       |
| > dataset format before GPU time                                           |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** train_uzbek.py \--dry_run exits 0 with dataset validation passing  |
| >                                                                          |
| > **✓** Effective batch size logged as 16 (4 × 4)                          |
| >                                                                          |
| > **✓** Output path resolves to /root/aziza/adapters/uz_colloquial/        |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-2.4 Execute QLoRA Training Run   | **PENDING**                      |
| --- Uzbek**                             |                                  |
|                                         | Owner: Chris / H100 (GPU time)   |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-2.3                                                   |
+----------------------------------------------------------------------------+
| **Objective:** Run the 3-stage curriculum QLoRA training on the H100.      |
| Estimated 12--18 hours. Monitor for OOM, NaN loss, and checkpoint saves.   |
| Produce aziza-adapter-final-uz.                                            |
|                                                                            |
| > **•** Check VRAM clear: nvidia-smi (need ≥30GB free before starting)     |
| >                                                                          |
| > **•** Start screen session: screen -S aziza-train-uz                     |
| >                                                                          |
| > **•** Export HF_TOKEN, then run: python3 train_uzbek.py \--register      |
| > colloquial \--dataset_path ./aziza-uzbek.jsonl \--output_base            |
| > /root/aziza/adapters                                                     |
| >                                                                          |
| > **•** Monitor: watch -n 10 nvidia-smi AND tail -f                        |
| > runs/uz_colloquial\_\*/trainer_log.jsonl                                 |
| >                                                                          |
| > **•** OOM fallback: add \--batch_size 2 \--grad_accum 8 (maintains       |
| > effective batch of 16)                                                   |
| >                                                                          |
| > **•** On completion: verify                                              |
| > /root/aziza/adapters/uz_colloquial/adapter_model.safetensors exists      |
| >                                                                          |
| > **•** Archive: tar -czf aziza-adapter-final-uz.tar.gz                    |
| > /root/aziza/adapters/uz_colloquial/                                      |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** Training completes all 3 stages with no CUDA OOM or NaN loss       |
| >                                                                          |
| > **✓** adapter_model.safetensors and adapter_config.json present in       |
| > output dir                                                               |
| >                                                                          |
| > **✓** aziza-adapter-final-uz.tar.gz created and stored off-GPU           |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-2.5 Write eval_uzbek.py and Run  | **PENDING**                      |
| Acceptance Gates**                      |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-2.4                                                   |
+----------------------------------------------------------------------------+
| **Objective:** Clone eval_russian.py into eval_uzbek.py. Replace           |
| Cyrillic-ratio metric with Uzbek script coverage metric. Run all 5         |
| acceptance gates. Must achieve ≥80% Uzbek script fidelity.                 |
|                                                                            |
| > **•** Copy eval_russian.py → eval_uzbek.py                               |
| >                                                                          |
| > **•** Replace has_cyrillic() with has_uzbek_script(): for Latin check    |
| > for ʻ (U+02BB) presence; for Cyrillic check for Ҳ Ҷ Қ Ғ Ў range          |
| >                                                                          |
| > **•** Replace RU_TEST_PROMPTS with 10 Uzbek prompts covering: greeting,  |
| > persona, academic, professional, cultural, business writing,             |
| > translation, AI explanation, everyday task, capability description ---   |
| > in target script                                                         |
| >                                                                          |
| > **•** Gate thresholds unchanged: adapter_loads=1.0, pass_rate≥0.8,       |
| > script_pct≥0.8, ttft_proxy, no_english_regression≥0.5                    |
| >                                                                          |
| > **•** Add language_switching gate: Latin input → Latin output, Cyrillic  |
| > input → Cyrillic output. Target ≥95%.                                    |
| >                                                                          |
| > **•** Run: python3 eval_uzbek.py \--adapter                              |
| > /root/aziza/adapters/uz_colloquial \--language uz_latin                  |
| >                                                                          |
| > **•** If pass_rate \< 0.8: rerun train_uzbek.py with \--register all to  |
| > use full dataset                                                         |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** Script fidelity ≥80% on held-out Uzbek test set                    |
| >                                                                          |
| > **✓** Language switching accuracy ≥95% (Latin→Latin, Cyrillic→Cyrillic)  |
| >                                                                          |
| > **✓** eval_uzbek_report.txt saved to adapter directory                   |
| >                                                                          |
| > **✓** All 5 gates pass. Exit code 0.                                     |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-2.6 TTFT Benchmark --- Combined  | **PENDING**                      |
| Adapters, Voice-First Validation**      |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-2.5                                                   |
+----------------------------------------------------------------------------+
| **Objective:** Write bench_ttft.py using StoppingCriteria hook to measure  |
| real Time-To-First-Token (not batch proxy). Target: p95 TTFT \<100ms       |
| across all three language modes simultaneously.                            |
|                                                                            |
| > **•** Write TTFTTimer(StoppingCriteria) class: record wall-clock time on |
| > first new token generated                                                |
| >                                                                          |
| > **•** Open WebSocket to serve_russian_test.py extended to accept         |
| > \--adapter_path arg                                                      |
| >                                                                          |
| > **•** Send 50 prompts alternating: Russian / Uzbek Latin / Uzbek         |
| > Cyrillic                                                                 |
| >                                                                          |
| > **•** Record: per-prompt TTFT_ms. Report: p50, p95, p99 for each         |
| > language + combined                                                      |
| >                                                                          |
| > **•** If p95 \> 100ms: investigate tokenizer extension overhead, NF4     |
| > cache miss on new tokens, Moshi buffer config                            |
| >                                                                          |
| > **•** Save bench_ttft_report.txt to /root/aziza/adapters/                |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** p95 TTFT \<100ms across all three language modes                   |
| >                                                                          |
| > **✓** No regression vs Russian-only baseline (p95 delta \<15ms)          |
| >                                                                          |
| > **✓** bench_ttft_report.txt saved with full percentile breakdown         |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-2.7 Extend API Gateway --- Uzbek | **PENDING**                      |
| Language Modes**                        |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-2.5                                                   |
+----------------------------------------------------------------------------+
| **Objective:** Update NestJS API Gateway session init to support uz-latin  |
| and uz-cyrillic as first-class language modes. Update PersonaPlex with     |
| Uzbek system prompts. Add Uzbek drift guard.                               |
|                                                                            |
| > **•** Add language field to session init payload: \"ru\" \| \"uz-latin\" |
| > \| \"uz-cyrillic\"                                                       |
| >                                                                          |
| > **•** Map uz-latin → PersonaPlex Uzbek Latin context (formal \"Siz\" +   |
| > \"sen\" register rules)                                                  |
| >                                                                          |
| > **•** Map uz-cyrillic → PersonaPlex Uzbek Cyrillic context               |
| >                                                                          |
| > **•** Uzbek drift guard: if response contains \>10% ASCII printable      |
| > chars (excl. digits/punct) in Uzbek mode → flag and retry once           |
| >                                                                          |
| > **•** Load correct adapter at session start based on language tag        |
| >                                                                          |
| > **•** Extend serve_russian_test.py to serve_multilingual.py: accepts     |
| > \--language arg, loads correct adapter                                   |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** POST /session with language: \"uz-latin\" returns Uzbek Latin      |
| > responses end-to-end                                                     |
| >                                                                          |
| > **✓** Language drift guard triggers retry on English-drifted responses   |
| >                                                                          |
| > **✓** PersonaPlex has separate context entries for uz-latin and          |
| > uz-cyrillic                                                              |
| >                                                                          |
| > **✓** /health endpoint reports all three adapter statuses                |
+----------------------------------------------------------------------------+

> **4. PHASE 3 --- PRODUCTION & ORCHESTRATOR INTEGRATION**

  ------------------------------------------------- ----------------
  **PHASE 3 Production Infrastructure**               **Foundation
                                                        Ready \|
                                                      Integration
                                                       Pending**

  ------------------------------------------------- ----------------

+-----------------------------------------+:--------------------------------:+
| **TASK-3.1 Orchestrator --- Dynamic GPU | **PENDING**                      |
| Worker Pool Routing**                   |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Objective:** Revise NestJS Orchestrator so session requests route        |
| directly to an idle GPU worker WebSocket URL. No session ever proxied      |
| through the Orchestrator. Redis-backed worker registry with atomic status  |
| transitions.                                                               |
|                                                                            |
| > **•** On worker startup: SET worker:{id}:status \"idle\" AND SET         |
| > worker:{id}:ws_url \"ws://\<host\>:\<port\>\" in Redis                   |
| >                                                                          |
| > **•** On POST /session: scan Redis for worker:\*:status = \"idle\", pick |
| > one atomically with GETSET worker:{id}:status \"busy\"                   |
| >                                                                          |
| > **•** Return {ws_url: \"ws://\...\"} directly to client. Client connects |
| > to worker directly.                                                      |
| >                                                                          |
| > **•** On session end: worker sets own status back to \"idle\" via        |
| > DELETE + SET                                                             |
| >                                                                          |
| > **•** If no idle workers: return 503 {error: \"all_workers_busy\",       |
| > retry_after: 5}                                                          |
| >                                                                          |
| > **•** Worker ID = PM2 app instance name (e.g., aziza-worker-0)           |
| >                                                                          |
| > **•** Add /workers/status admin endpoint showing all workers and their   |
| > current state                                                            |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** POST /session returns {ws_url} pointing directly to idle worker    |
| >                                                                          |
| > **✓** Worker status transitions verified via Redis CLI: idle → busy →    |
| > idle                                                                     |
| >                                                                          |
| > **✓** N simultaneous session requests satisfied with 0 queuing (N =      |
| > running PM2 worker count)                                                |
| >                                                                          |
| > **✓** 503 returned cleanly when all workers busy                         |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-3.2 Voice Frontend ---           | **PENDING**                      |
| AudioWorklet + WebSocket Browser        |                                  |
| Client**                                | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-3.1                                                   |
+----------------------------------------------------------------------------+
| **Objective:** Build the browser-side voice client in Vue 3.               |
| AudioWorkletProcessor captures mic at 16kHz, streams PCM frames over       |
| WebSocket to Moshi worker. Receives PCM audio frames back and plays them   |
| via AudioBufferSourceNode queue. This enables both Voice→Text and          |
| Voice↔Voice modes in the browser.                                          |
|                                                                            |
| > **•** AudioWorkletProcessor: 40ms PCM frames at 16kHz mono. Post to main |
| > thread via port.postMessage().                                           |
| >                                                                          |
| > **•** Main thread: WebSocket to worker ws_url from Orchestrator. Send    |
| > binary PCM frames.                                                       |
| >                                                                          |
| > **•** Receive binary frames from Moshi: feed into AudioPlaybackQueue     |
| > using scheduled AudioBufferSourceNode.                                   |
| >                                                                          |
| > **•** AudioContext sample rate: detect browser native rate (usually      |
| > 48kHz), resample to 16kHz for send, resample Moshi 24kHz output to       |
| > native for playback using linear interpolation.                          |
| >                                                                          |
| > **•** Vue component: \<VoiceChat\> with states: idle / connecting /      |
| > listening / speaking / error                                             |
| >                                                                          |
| > **•** Show real-time transcript overlay while Moshi generates text       |
| > alongside audio.                                                         |
| >                                                                          |
| > **•** Language selector dropdown: Russian / Uzbek Latin / Uzbek Cyrillic |
| > --- sets session language on connect.                                    |
| >                                                                          |
| > **•** Full-duplex indicator: show when both mic active AND audio playing |
| > (true duplex mode).                                                      |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** Browser mic input → Moshi → audio playback working end-to-end with |
| > \<300ms perceived latency                                                |
| >                                                                          |
| > **✓** No audio glitches or gaps during 5-minute continuous voice session |
| >                                                                          |
| > **✓** Language switching works by ending session and starting new one    |
| > with correct language tag                                                |
| >                                                                          |
| > **✓** Voice→Text mode: response displayed as text + optionally spoken    |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-3.3 Asterisk ARI Bridge --- RTP  | **PENDING**                      |
| → WebSocket Audio Pipeline**            |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-3.1                                                   |
+----------------------------------------------------------------------------+
| **Objective:** Build Python + asyncio service (asterisk_ari_bridge.py)     |
| connecting Asterisk ARI to Moshi inference. Enables real phone calls       |
| through the full Aziza AI stack.                                           |
|                                                                            |
| > **•** Connect to Asterisk ARI: aiohttp WebSocket to                      |
| > http://localhost:8088/ari. Subscribe to StasisStart on app \"aziza\".    |
| >                                                                          |
| > **•** On incoming call: answer channel, initiate ExternalMedia RTP       |
| > stream on local UDP port.                                                |
| >                                                                          |
| > **•** FFmpeg subprocess: asyncio.subprocess, receive RTP on UDP port,    |
| > transcode to 16kHz mono PCM, pipe to stdout.                             |
| >                                                                          |
| > **•** Read PCM chunks from FFmpeg stdout → asyncio queue → WebSocket     |
| > binary frames to Moshi worker URL.                                       |
| >                                                                          |
| > **•** Receive Moshi response PCM → reverse FFmpeg transcode to G.711     |
| > ulaw → RTP back to Asterisk channel.                                     |
| >                                                                          |
| > **•** Full duplex: continue reading mic RTP while Moshi audio is playing |
| > (no half-duplex blocking).                                               |
| >                                                                          |
| > **•** Error handling: Moshi WS disconnect → hold tone + reconnect once.  |
| > ARI channel drop → cancel all tasks cleanly.                             |
| >                                                                          |
| > **•** No sync requests anywhere --- entire service is                    |
| > asyncio/aiohttp/websockets.                                              |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** Incoming SIP call → StasisStart → bridge connects → Moshi responds |
| > in correct language                                                      |
| >                                                                          |
| > **✓** Audio round-trip latency ≤300ms LAN (phone mic → Moshi → phone     |
| > speaker)                                                                 |
| >                                                                          |
| > **✓** Service survives 10 consecutive calls with no memory leak or       |
| > zombie FFmpeg processes                                                  |
| >                                                                          |
| > **✓** Language detection: ARI channel variable AZIZA_LANGUAGE used to    |
| > set session language                                                     |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-3.4 PM2 Ecosystem Config --- All | **PENDING**                      |
| Production Processes**                  |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-3.1 → TASK-3.3                                        |
+----------------------------------------------------------------------------+
| **Objective:** Write ecosystem.config.js defining every production         |
| process. Single pm2 start ecosystem.config.js brings up the complete       |
| stack. Must survive server reboot via pm2 save + pm2 startup.              |
|                                                                            |
| > **•** aziza-gateway: NestJS API Gateway, port 3000, env: REDIS_URL,      |
| > JWT_SECRET                                                               |
| >                                                                          |
| > **•** aziza-orchestrator: session routing service                        |
| >                                                                          |
| > **•** aziza-worker-0 through aziza-worker-N: Moshi inference workers.    |
| > Each with WORKER_ID and WS_PORT env vars. Startup hook registers ws_url  |
| > in Redis.                                                                |
| >                                                                          |
| > **•** aziza-ari-bridge: Asterisk bridge service (asterisk_ari_bridge.py) |
| >                                                                          |
| > **•** aziza-personaplex: PersonaPlex microservice                        |
| >                                                                          |
| > **•** aziza-frontend: static file serving (serve dist/ on port 8010)     |
| >                                                                          |
| > **•** Each worker startup script: register in Redis before PM2 marks     |
| > online                                                                   |
| >                                                                          |
| > **•** pm2 save + pm2 startup generates systemd unit. Test with server    |
| > reboot.                                                                  |
| >                                                                          |
| > **•** Adding new worker: increment N in config, pm2 reload --- zero      |
| > downtime.                                                                |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** pm2 start ecosystem.config.js: all services online, 0 restarts in  |
| > first 60s                                                                |
| >                                                                          |
| > **✓** pm2 save + pm2 startup survives reboot                             |
| >                                                                          |
| > **✓** pm2 status shows all 6+ processes as online                        |
| >                                                                          |
| > **✓** Redis shows all workers registered with idle status after startup  |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-3.5 Git Repository ---           | **PENDING**                      |
| Production Config + Branch Strategy**   |                                  |
|                                         | Owner: Chris                     |
+-----------------------------------------+----------------------------------+
| **Objective:** Create the permanent Git repository. Commit all existing    |
| assets to dev branch. Establish branch protections and PR workflow for     |
| team collaboration.                                                        |
|                                                                            |
| > **•** Create repo aziza-platform (private)                               |
| >                                                                          |
| > **•** Directories: /gateway /orchestrator /inference /telephony          |
| > /training /personaplex /frontend                                         |
| >                                                                          |
| > **•** /training: train_russian.py, train_uzbek.py, eval\_\*.py,          |
| > bench_ttft.py, audit_tokenizer.py, validate_uzbek_dataset.py             |
| >                                                                          |
| > **•** Root files: ecosystem.config.js, .env.example (all env vars        |
| > documented, no secrets), README.md                                       |
| >                                                                          |
| > **•** .gitignore: \*.safetensors, \*.tar.gz, \*.jsonl, .env,             |
| > node_modules/, \_\_pycache\_\_/, runs/, rag_index/                       |
| >                                                                          |
| > **•** Branch strategy: main=production (protected, no direct push),      |
| > dev=integration, feature/task-{id}-{slug}                                |
| >                                                                          |
| > **•** PR rules: feature/\* → dev requires 1 review. dev → main requires  |
| > passing E2E test result attached.                                        |
| >                                                                          |
| > **•** CONTRIBUTING.md: branch naming, PR checklist, env setup            |
| > instructions                                                             |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** Repo created with all existing assets committed to dev             |
| >                                                                          |
| > **✓** main branch protection enabled                                     |
| >                                                                          |
| > **✓** .gitignore excludes all model weights and datasets                 |
| >                                                                          |
| > **✓** CONTRIBUTING.md documents full workflow                            |
+----------------------------------------------------------------------------+

+-----------------------------------------+:--------------------------------:+
| **TASK-3.6 End-to-End Integration Test  | **PENDING**                      |
| --- All Three Modes**                   |                                  |
|                                         | Owner: Chris + Ivan              |
+-----------------------------------------+----------------------------------+
| **Depends on:** TASK-2.7 → TASK-3.1 → TASK-3.2 → TASK-3.3 → TASK-3.4       |
+----------------------------------------------------------------------------+
| **Objective:** Final acceptance test covering all three interaction modes  |
| in both Russian and Uzbek. This is the milestone completion gate for Ivan. |
|                                                                            |
| > **•** TEXT→TEXT: POST /chat with Russian + Uzbek Latin + Uzbek Cyrillic  |
| > prompts. Assert: correct script response, \<3000ms, coherent.            |
| >                                                                          |
| > **•** VOICE→TEXT: Browser mic → speak Russian sentence → assert Cyrillic |
| > transcript appears within 2s of end-of-speech.                           |
| >                                                                          |
| > **•** VOICE↔VOICE BROWSER: Open voice session, speak greeting in Russian |
| > → hear Aziza respond in Russian audio. Repeat in Uzbek.                  |
| >                                                                          |
| > **•** VOICE↔VOICE PHONE: Dial SIP trunk DID, speak Russian → Aziza       |
| > responds. Speak Uzbek → Aziza responds in Uzbek. Record both sides.      |
| >                                                                          |
| > **•** Monitor during test: pm2 logs tailing all workers, Redis worker    |
| > status transitions, no uncaught exceptions.                              |
| >                                                                          |
| > **•** Assert phone round-trip latency \<300ms (Asterisk MixMonitor       |
| > timestamp vs first audio byte).                                          |
| >                                                                          |
| > **•** Run all 3 modes for 10 minutes continuous without crash or memory  |
| > leak.                                                                    |
+----------------------------------------------------------------------------+
| **ACCEPTANCE CRITERIA**                                                    |
|                                                                            |
| > **✓** All 3 modes working in both Russian and Uzbek without intervention |
| >                                                                          |
| > **✓** Text→Text: \<3s response, correct script, coherent language        |
| >                                                                          |
| > **✓** Voice→Text: transcript appears \<2s after end-of-speech            |
| >                                                                          |
| > **✓** Voice↔Voice: audio round-trip \<300ms, no glitches in 10-min       |
| > session                                                                  |
| >                                                                          |
| > **✓** Phone call: SIP→Asterisk→Moshi→SIP working end-to-end              |
| >                                                                          |
| > **✓** Test results documented in /tests/e2e/results/ with timestamps     |
+----------------------------------------------------------------------------+

> **5. EXECUTION SEQUENCE & CRITICAL PATH**

  -------- ----------------- ------------------ -------------------------
  **\#**   **Tasks**         **Parallel With**  **Notes**

  **1**    TASK-2.1          TASK-3.5 (git      UNBLOCKS everything in
           (tokenizer audit) setup)             Phase 2. Run tonight.

  **2**    TASK-2.2 (dataset TASK-3.4 (PM2      Download HuggingFace
           prep)             config)            datasets, format,
                                                validate.

  **3**    TASK-2.3 (write   ---                30-minute task. Clone +
           train_uzbek.py)                      minimal edits.

  **4**    TASK-2.4 (Uzbek   TASK-3.1 +         12-18hrs GPU time. Run
           training run)     TASK-3.2 +         overnight. Work on Phase
                             TASK-3.3           3 in parallel.

  **5**    TASK-2.5          TASK-3.3 (ARI      Run morning after
           (eval_uzbek.py)   bridge)            training. \~15 min.

  **6**    TASK-2.6 (TTFT    TASK-3.4 (PM2      Run after eval passes.
           benchmark)        config)            

  **7**    TASK-2.7 (API     ---                NestJS language routing +
           Gateway Uzbek)                       PersonaPlex Uzbek
                                                prompts.

  **8**    TASK-3.1          TASK-2.4 training  Can build while GPU is
           (Orchestrator     run                training.
           routing)                             

  **9**    TASK-3.2 (Voice   TASK-2.4 training  Vue 3 AudioWorklet
           frontend)         run                component. Can build
                                                while GPU trains.

  **10**   TASK-3.3 (ARI     TASK-2.4 training  Critical path for phone
           bridge)           run                mode. Build in parallel.

  **11**   TASK-3.4 (PM2     TASK-2.4 training  Write ecosystem.config.js
           ecosystem)        run                while GPU trains.

  **12**   TASK-3.6 (E2E     ---                All tasks above must be
           test --- FINAL)                      complete. Ivan milestone
                                                gate.
  -------- ----------------- ------------------ -------------------------

  -----------------------------------------------------------------
  **CRITICAL PATH:** TASK-2.1 → TASK-2.2 → TASK-2.3 → TASK-2.4 →
  TASK-2.5 → TASK-2.7 → TASK-3.6. Everything on the critical path
  is sequential and GPU-bound. Phase 3 tasks (3.1, 3.2, 3.3, 3.4)
  should be built IN PARALLEL during the 12-18hr Uzbek training
  window.

  -----------------------------------------------------------------

> **6. ENVIRONMENT & CONFIGURATION REFERENCE**

**6.1 Required Environment Variables**

  -------------------------- ------------------------------------------ -------------------------
  **Variable**               **Example Value**                          **Used By**

  HF_TOKEN                   hf_xxxxxxxxxxxx                            All training + serving
                                                                        scripts

  MODEL_ID                   Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24                     serve_multilingual.py,
                                                                        eval scripts

  ADAPTER_PATH_RU            /root/aziza/adapters/ru_colloquial         serve_multilingual.py

  ADAPTER_PATH_UZ_LATIN      /root/aziza/adapters/uz_colloquial         serve_multilingual.py

  ADAPTER_PATH_UZ_CYRILLIC   /root/aziza/adapters/uz_cyrillic           serve_multilingual.py

  REDIS_URL                  redis://localhost:6379                     NestJS Gateway,
                                                                        Orchestrator

  JWT_SECRET                 \<random 64-char hex\>                     NestJS Gateway auth

  DATABASE_URL               postgresql://aziza:pw@localhost/aziza_db   Backend server.py

  WORKER_ID                  aziza-worker-0                             Each Moshi worker process

  WS_PORT                    8021 (8021, 8022, 8023\...)                Each Moshi worker
                                                                        (increment per instance)

  ASTERISK_URL               http://localhost:8088                      asterisk_ari_bridge.py

  ASTERISK_USER              aziza                                      ARI auth

  ASTERISK_PASS              \<ari password\>                           ARI auth
  -------------------------- ------------------------------------------ -------------------------

**6.2 Locked Training Config --- Do Not Change**

> LOCKED_CONFIG = {
>
> \"lora_r\": 16,
>
> \"lora_alpha\": 32,
>
> \"lora_dropout\": 0.05,
>
> \"target_modules\": \[\"q_proj\", \"v_proj\", \"k_proj\",
> \"o_proj\"\],
>
> \"max_seq_length\": 512,
>
> \"batch_size\": 4,
>
> \"grad_accum_steps\": 4, \# effective batch = 16
>
> \"learning_rate\": 2e-4,
>
> \"num_epochs\": 3,
>
> \"lr_scheduler_type\": \"cosine\",
>
> \"quantization\": \"nf4\", \# 4-bit NF4
>
> \"double_quant\": True,
>
> \"compute_dtype\": \"float16\",
>
> }

**6.3 HuggingFace Dataset Load Commands**

> from datasets import load_dataset
>
> \# Uzbek Latin --- Primary (52K instruction pairs)
>
> uz_primary = load_dataset(\"behbudiy/alpaca-cleaned-uz\")
>
> \# Uzbek Latin --- Secondary (52K, independent translation)
>
> uz_secondary = load_dataset(\"saillab/alpaca-uzbek-cleaned\")
>
> \# Uzbek Bilingual --- Professional register (20K, higher quality)
>
> uz_bilingual = load_dataset(\"behbudiy/translation-instruction\")
>
> \# Uzbek Cyrillic --- Book corpus (Latin+Cyrillic, 40K books)
>
> uz_books = load_dataset(\"tahrirchi/uz-books\")
>
> \# Russian supplement if needed
>
> ru_dialogues = load_dataset(\"Den4ikAI/russian_dialogues\")
>
> **7. FINAL PRODUCTION ACCEPTANCE CHECKLIST**

Every item below must be checked before declaring the system
production-ready and presenting to Ivan.

  ---- ---------------------------------------- ------------ -----------------------
       **Acceptance Item**                      **Status**   **Evidence**

  □    Russian QLoRA adapter eval passed (≥80%  ✅ Done      eval_results.json
       Cyrillic accuracy)                                    

  □    Uzbek Latin QLoRA adapter eval passed    ❌ Pending   
       (≥80% accuracy)                                       

  □    Uzbek Cyrillic QLoRA adapter eval passed ❌ Pending   
       (≥80% accuracy)                                       

  □    TTFT p95 \<100ms --- Russian             ✅ Done      bench_ttft_report.txt

  □    TTFT p95 \<100ms --- Uzbek Latin         ❌ Pending   

  □    TTFT p95 \<100ms --- Uzbek Cyrillic      ❌ Pending   

  □    Text→Text: Russian coherent response in  ✅ Done      smoke test /chat
       \<3s                                                  

  □    Text→Text: Uzbek Latin coherent response ❌ Pending   
       in \<3s                                               

  □    Text→Text: Uzbek Cyrillic coherent       ❌ Pending   
       response in \<3s                                      

  □    Voice→Text: transcript \<2s after        ❌ Pending   
       end-of-speech (Russian)                               

  □    Voice→Text: transcript \<2s after        ❌ Pending   
       end-of-speech (Uzbek)                                 

  □    Voice↔Voice browser: audio round-trip    ❌ Pending   
       \<300ms (Russian)                                     

  □    Voice↔Voice browser: audio round-trip    ❌ Pending   
       \<300ms (Uzbek)                                       

  □    Voice↔Voice phone (SIP): end-to-end call ❌ Pending   
       working (Russian)                                     

  □    Voice↔Voice phone (SIP): end-to-end call ❌ Pending   
       working (Uzbek)                                       

  □    PersonaPlex: Aziza stays in character 5+ ✅ Done      eval gate 5
       turns (Russian)                                       

  □    PersonaPlex: Aziza stays in character 5+ ❌ Pending   
       turns (Uzbek)                                         

  □    10-minute continuous session --- no      ❌ Pending   
       crash, no memory leak                                 

  □    PM2 ecosystem starts all services from   ❌ Pending   
       cold boot                                             

  □    Git repo created, all assets committed,  ❌ Pending   
       branch protection on                                  

  □    All adapter .tar.gz backups stored       RU ✅ / UZ   
       off-GPU                                  ❌           
  ---- ---------------------------------------- ------------ -----------------------

AZIZA AI PLATFORM --- MASTER BUILD PROMPT · Novatech · Confidential ·
June 2026
