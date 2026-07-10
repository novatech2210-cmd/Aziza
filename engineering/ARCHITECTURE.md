# AZIZA Architecture

## Core Principles
1. **Low Latency:** First-token latency must remain under 2s for voice pipelines.
2. **Microservices:** Separation of text generation, ASR, and V2V routing.
3. **Immutability:** The architecture is frozen. No new databases, frameworks, or languages may be added without human approval.

## Components
- Gateway: WebSocket routing layer for inference requests.
- Worker: vLLM or specialized model inference endpoints.
- DB: PersonaPlex dynamic persona storage.
