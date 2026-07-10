MASTER BUILD PROMPT — AZIZA REAL-TIME MULTILINGUAL VOICE AI PLATFORM WITH PERSONAPLEX

You are a senior distributed systems architect, AI infrastructure engineer, real-time voice systems engineer, GPU optimization engineer, and conversational AI orchestration engineer.

Your task is to build a production-grade multilingual real-time AI voice platform named “Aziza”.

The frontend already exists.

You must build the ENTIRE backend, orchestration layer, streaming pipeline, inference infrastructure, PersonaPlex memory system, and production deployment architecture in the CORRECT IMPLEMENTATION ORDER.

The platform MUST prioritize:

ultra-low latency
streaming-first architecture
concurrent session stability
GPU optimization
modular microservices
telephony support
persona persistence
multilingual conversations
long-term memory
production scalability
Dockerized deployment

DO NOT:

start with fine-tuning
start with personas before infrastructure
embed persona logic inside inference runtime
build synchronous pipelines
create monolithic architecture

The system MUST be modular and production-grade.

PRIMARY OBJECTIVES

The system must support:

real-time duplex AI voice conversations
multilingual streaming conversations
persistent personas
long-term conversational memory
frontend voice interaction
telephony-based AI calls
concurrent GPU-backed sessions
streaming token generation
low-latency orchestration
Redis-backed session routing
Dockerized deployment
horizontal scalability
REQUIRED TECH STACK
Frontend
Existing frontend already provided
Next.js
React
WebSocket client
BACKEND STACK
Core Backend
NestJS
FastAPI
Python
Socket.IO
WebSocket
Redis
MongoDB
NGINX
Docker
Docker Compose
AI STACK
Runtime
Moshi
Hugging Face Transformers
PyTorch CUDA
transformer-engine
vLLM or TGI
Fine-Tuning
PEFT
LoRA
QLoRA
bitsandbytes
datasets
accelerate
AUDIO / STREAMING STACK
WebRTC
FFmpeg
RTP
Asterisk ARI
SIP integration
GPU REQUIREMENTS

Target GPUs:

L40S
A100
H100
RTX 4090 minimum

Must support:

FP8 inference
CUDA streams
dynamic batching
concurrent streaming inference
COMPLETE SYSTEM ARCHITECTURE

Use this architecture EXACTLY:

Frontend
↓
NGINX Gateway
↓
NestJS API Gateway
↓
WebSocket Session Layer
↓
PersonaPlex Service
↓
AI Orchestrator
↓
Redis Queue Layer
↓
Moshi Streaming Runtime
↓
LLM Inference Runtime
↓
Audio Response Stream
↓
Frontend + Telephony Clients
CORE SERVICES

Build the following isolated services:

1. API Gateway Service

Responsibilities:

authentication
session management
websocket handling
API routing
rate limiting
external client communication

Tech:

NestJS
Socket.IO
JWT
2. PersonaPlex Service

Responsibilities:

persona orchestration
memory persistence
prompt assembly
contextual recall
multilingual personality adaptation
emotional state tracking
session continuity

Tech:

FastAPI
Redis
MongoDB
3. AI Orchestrator

Responsibilities:

stream routing
session lifecycle
GPU scheduling
worker allocation
inference coordination
Redis pub/sub coordination

Tech:

Python
Redis
asyncio
4. Moshi Streaming Runtime

Responsibilities:

streaming inference
token generation
audio streaming
real-time response generation
async inference execution

Tech:

PyTorch
CUDA
Hugging Face
Moshi
5. Redis Layer

Responsibilities:

active session cache
pub/sub messaging
queue coordination
stream buffering
hot memory cache
6. MongoDB Layer

Responsibilities:

long-term memory
conversation history
persona persistence
analytics
summarized memory storage
7. Telephony Service

Responsibilities:

Asterisk integration
RTP bridging
SIP handling
call lifecycle management
IMPLEMENTATION ORDER (MANDATORY)

DO NOT skip phases.

DO NOT start future phases before previous phases are validated.

PHASE 1 — INFRASTRUCTURE FOUNDATION

Goal:
Create stable GPU-enabled backend infrastructure.

Tasks:

Create Dockerized architecture
Configure Docker Compose
Configure NVIDIA Container Toolkit
Verify GPU visibility inside containers
Setup Redis
Setup MongoDB
Setup NGINX reverse proxy
Setup environment configuration
Setup centralized logging
Setup monitoring foundation

Deliverables:

operational Docker environment
GPU-enabled containers
Redis operational
MongoDB operational
NGINX routing operational

Validation:

containers restart safely
GPU accessible in containers
Redis persistence operational
Mongo persistence operational
PHASE 2 — API GATEWAY

Goal:
Build backend communication foundation.

Tasks:

Build NestJS API gateway
Add JWT authentication
Add refresh tokens
Add session management
Add rate limiting
Add websocket gateway
Add request validation
Add health endpoints
Add structured logging

Endpoints:

/auth
/session
/stream/start
/stream/stop
/persona
/health

Deliverables:

stable API gateway
websocket communication
authentication system

Validation:

websocket stability
JWT auth operational
session tracking operational
PHASE 3 — REAL-TIME STREAMING FOUNDATION

Goal:
Establish real-time duplex audio streaming.

Tasks:

Build websocket audio pipeline
Build audio chunk streaming
Add FFmpeg transcoding
Add async audio queues
Add reconnect handling
Add interruption handling
Add stream synchronization
Add buffering controls

Requirements:

async architecture
low jitter
low latency
non-blocking streaming

Deliverables:

real-time audio streaming pipeline

Validation:

no desync
stable streaming
low latency maintained
PHASE 4 — MOSHI INFERENCE RUNTIME

Goal:
Deploy streaming AI inference runtime.

Tasks:

Deploy Moshi runtime
Load Hugging Face models
Configure CUDA inference
Add token streaming
Add async generation
Add tokenizer management
Add KV-cache optimization
Add inference memory management

Requirements:

streaming-first inference
async execution
token-level streaming

Deliverables:

functional streaming inference runtime

Validation:

stable token generation
no memory leaks
real-time inference operational
PHASE 5 — GPU OPTIMIZATION

Goal:
Scale concurrent AI sessions.

Tasks:

Enable FP8 support
Install transformer-engine
Add CUDA stream optimization
Add dynamic batching
Add GPU scheduler
Add memory pooling
Add inference queue balancing
Add latency monitoring

Performance Targets:

8–10 concurrent sessions
<120ms latency target

Deliverables:

optimized GPU inference runtime

Validation:

stable concurrent sessions
no CUDA OOM
no inference starvation
PHASE 6 — PERSONAPLEX INTEGRATION

Goal:
Build persistent persona orchestration and long-term memory layer.

PersonaPlex MUST exist as an isolated microservice.

DO NOT embed persona logic inside:

frontend
Moshi
inference runtime
websocket layer

Tasks:

Deploy PersonaPlex service
Add persona profile management
Add long-term memory persistence
Add Redis-backed hot memory cache
Add contextual prompt assembly
Add multilingual persona adaptation
Add emotional state tracking
Add session continuity
Add memory summarization workers
Add prompt injection middleware

PersonaPlex APIs:

POST /persona/load
POST /persona/switch
GET /persona/state
POST /memory/store
POST /memory/retrieve
POST /prompt/build

Requirements:

async architecture
Redis-first retrieval
low-latency prompt assembly
streaming-safe context windows

Performance Target:

<30ms prompt assembly overhead

Deliverables:

persistent persona system
long-term memory system
contextual orchestration layer

Validation:

persona consistency maintained
memory persists across sessions
multilingual memory operational
no inference blocking
PHASE 7 — AI ORCHESTRATOR

Goal:
Coordinate all runtime services.

Tasks:

Build orchestration service
Add session routing
Add stream lifecycle management
Add GPU worker allocation
Add Redis pub/sub coordination
Add inference scheduling
Add service discovery
Add failover handling

Deliverables:

centralized orchestration system

Validation:

sessions isolated correctly
stable routing
no cross-session leakage
PHASE 8 — FRONTEND INTEGRATION [COMPLETED]

Goal:
Connect backend to existing frontend.

Tasks:

[x] Connect websocket streams
[x] Connect auth system
[x] Connect streaming controls
[x] Add reconnect logic
[x] Add event synchronization
[x] Add session state syncing

Deliverables:

[x] full frontend/backend communication

Validation:

[x] stable streaming interaction
[x] frontend synchronization operational
PHASE 9 — TELEPHONY INTEGRATION

Goal:
Enable AI voice calls through telephony.

Tasks:

Integrate Asterisk ARI
Build RTP bridge
Add SIP session handling
Add telephony stream routing
Add reconnect handling
Add call lifecycle management
Add recording controls

Deliverables:

telephony AI runtime

Validation:

stable phone calls
low-latency RTP streaming
no telephony desync
PHASE 10 — MONITORING & OBSERVABILITY

Goal:
Production-grade monitoring stack.

Tasks:

Add Prometheus
Add Grafana
Add Loki
Add GPU monitoring
Add Redis monitoring
Add websocket monitoring
Add latency dashboards
Add error tracking

Monitor:

GPU memory
latency
queue delays
websocket failures
CUDA errors
token throughput

Deliverables:

observability stack

Validation:

live dashboards operational
actionable alerts available
PHASE 11 — MULTILINGUAL FINE-TUNING

ONLY START AFTER ALL PREVIOUS PHASES ARE STABLE.

Goal:
Create multilingual conversational personas.

Languages:

Russian
Uzbek Latin
Uzbek Cyrillic
English

Tasks:

Prepare datasets
Audit tokenizer
Extend tokenizer if necessary
Train LoRA adapters
Optimize inference compatibility
Validate streaming quality
Validate multilingual response quality

Requirements:

maintain low latency
maintain streaming stability
small adapter sizes

Deliverables:

multilingual fine-tuned adapters

Validation:

natural multilingual responses
stable streaming maintained
REDIS MEMORY STRATEGY
Hot Cache

Store:

active context
current conversation window
emotional state
persona modifiers
stream-safe summaries
Cold Storage

Persist:

summarized memories
conversation history
user interaction history
persona evolution
PERSONAPLEX SESSION MODEL
{
  "session_id": "",
  "user_id": "",
  "persona_id": "",
  "language": "",
  "emotion_state": "",
  "conversation_summary": "",
  "active_context_window": [],
  "memory_refs": []
}
SECURITY REQUIREMENTS

Implement:

JWT authentication
HTTPS
Redis authentication
Mongo authentication
WebSocket authentication
container isolation
environment-based secrets
internal API authentication

NEVER hardcode:

API keys
Hugging Face tokens
database credentials

PersonaPlex MUST NOT be publicly exposed.

Only API Gateway may communicate externally.

PERFORMANCE REQUIREMENTS

The platform MUST:

support concurrent streaming sessions
support token-level streaming
avoid synchronous pipelines
avoid blocking inference
support async orchestration
support horizontal scaling

Use:

asyncio
queue-based architecture
Redis pub/sub
GPU-aware scheduling
dynamic batching
DEPLOYMENT REQUIREMENTS

Everything MUST be:

Dockerized
reproducible
production-ready
environment-configurable
horizontally scalable

Provide:

Dockerfiles
docker-compose.yml
.env.example
deployment scripts
health checks
REQUIRED OUTPUT AFTER EACH PHASE

At the end of every phase provide:

architecture summary
folder structure
source code
Docker configuration
deployment instructions
testing steps
validation checklist
known limitations
performance metrics

DO NOT continue to the next phase until the current phase is validated successfully.

Optimize for:

stability
low latency
streaming reliability
scalability
production readiness
multilingual conversational quality
