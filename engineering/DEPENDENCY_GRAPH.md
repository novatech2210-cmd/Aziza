# Dependency Graph

```mermaid
graph TD
    Client --> Cloudflare
    Cloudflare --> APIGateway
    APIGateway --> TelephonyBridge
    APIGateway --> Orchestrator
    Orchestrator --> Redis
    Orchestrator --> MongoDB
    Orchestrator --> PersonaPlex
    Orchestrator --> InferenceWorkers
    InferenceWorkers --> Models
```
