# Architecture Baseline Snapshot

## System Overview
AZIZA is an AI assistant relying on Moshi for native Russian/Uzbek phonetic pronunciation, combined with low-latency Voice-to-Voice and Text-to-Text pipelines.

## Components
1. **Gateways:** WebSocket interfaces for streaming audio and text.
2. **Workers:** vLLM instances for text, Moshi for audio.
3. **Storage:** PersonaPlex DB for persona states, Redis for caching/sessions.

## Flow
User -> Cloudflare -> Nginx -> FastAPI Gateway -> PersonaPlex -> vLLM / Moshi Worker -> Response Pipeline.
