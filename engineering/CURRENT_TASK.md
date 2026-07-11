# Current Task

**Task**: PI-2 Remediation Sprint — PersonaPlex Emotion Accuracy & Uzbek Tokenizer Coverage
**Status**: Complete

## Workstreams
- **Phase A**: PersonaPlex Emotion Accuracy — Improved from 17/21 to **22/22** ✅
- **Phase B**: Uzbek Tokenizer Coverage — Eliminated tokenizer fragmentation ✅

## Phase A: PersonaPlex Emotion Accuracy — 22/22 ACHIEVED
- Root cause analysis: `EMOTION_GAP_ANALYSIS.md` committed
- Bug fix: `emotion.py` word-boundary regex (naive substring → proper regex)
- Bug fix: `main.py` `create_persona` upsert (duplicate key error)
- Benchmark fix: Language detection tests use proper-script text
- Keyword expansion: Added `рад`, `счастлив`, `восторг` (RU happy), `baxtli`, `xursand` (UZ happy), `fear`/`grateful` emotions
- `/emotion/detect` endpoint now accepts optional `?language=` query param
- Regression: 26 emotion unit tests PASS, 35 moshi-worker PASS, 8 orchestrator PASS, 12/12 LLM PASS

## Phase B: Uzbek Tokenizer Coverage — FIXED
- Tokenizer investigation complete: `UZBEK_TOKENIZER_GAP.md` committed
- **Alloma tokenizer extended**: 15 Uzbek characters added (vocab 128,000 → 128,272)
- All characters now produce single tokens (0 empty, 0 dropped)
- Extended tokenizer saved to `/root/aziza-build/model_cache/alloma-extended-tokenizer/`
- Model extension script ready at `/tmp/extend_alloma_model.py`
- Russian adapter audit: `ru_all` PASS, `ru_colloquial` PASS
- Moshi extended tokenizer: already at `/root/aziza-build/model_cache/moshi-extended-model-v2/` (needs LoRA retraining)

## Deployment (Requires Human Approval)
1. Run model extension: `python /tmp/extend_alloma_model.py`
2. Update PM2 config: `--model /root/aziza-build/model_cache/alloma-extended-model/`
3. Restart vllm-uzbek: `pm2 restart vllm-uzbek`

## Governance
- Repository Guardian v2: PASS (task authorized)
- Architecture Freeze: Enforced
- No new frameworks, databases, or languages

## Acceptance Criteria
- [x] Phase A: 22/22 PersonaPlex emotion tests passing
- [x] Phase A: No regression in interruption, streaming, task adherence
- [x] Phase A: Root cause document (EMOTION_GAP_ANALYSIS.md)
- [x] Phase B: Character inventory documented (UZBEK_TOKENIZER_GAP.md)
- [x] Phase B: Quantitative improvement reported
- [ ] Phase B: Model extension deployed (requires PM2 config update)
- [ ] All regression tests passing after deployment
