# CORD: Voice Persuasion Agent — Design Document

**Date**: 2026-03-02
**Status**: Approved

## Problem Statement

Build a voice agent that calls an MIT student and convinces them to buy a pen. The system should support real phone calls (Twilio), a web-based dashboard for monitoring and analysis, and progressively scale into a distributed system for concurrent call handling.

## Use Cases

1. **Primary**: Persuasion agent — call a target, build rapport using researched personal info, pitch a pen sale, handle objections, close the deal, and arrange logistics (when/where to meet)
2. **Future**: Friend coordinator — call/text multiple friends to organize event scheduling

## Architecture: Chat-Supervisor Modular Monolith

Dual-model pattern based on OpenAI's Realtime Agents reference architecture:
- **Realtime Voice Model** (gpt-4o-mini-realtime): Handles natural conversation flow, greetings, rapport, delivery
- **Supervisor Model** (GPT-4.1, text): Makes strategic decisions — persuasion strategy, tool calls, stage transitions, profile lookups

The system starts as a modular monolith with clean internal boundaries, designed for progressive decomposition into microservices.

### System Diagram

```
                          +----------------------+
                          |    Next.js 15        |
                          |  Frontend Dashboard  |
                          +----------+-----------+
                                     | WebSocket + REST
                                     v
+------------------------------------------------------------+
|                    FastAPI Gateway                          |
|                                                            |
|  +-----------------------------------------------------+  |
|  |              Voice Pipeline                          |  |
|  |                                                      |  |
|  |  Twilio <-> Media Stream <-> OpenAI Realtime (voice) |  |
|  |  (or browser mic)          gpt-4o-mini-realtime      |  |
|  |                                   |                  |  |
|  |                          delegates complex tasks     |  |
|  |                                   v                  |  |
|  |                         OpenAI Supervisor (text)     |  |
|  |                           GPT-4.1                    |  |
|  |                           - persuasion strategy      |  |
|  |                           - tool calls               |  |
|  |                           - stage transitions        |  |
|  +-----------------------------------------------------+  |
|                                                            |
|  +--------------+  +--------------+  +---------------+     |
|  | Research     |  | Call Manager |  | Conversation  |     |
|  | Module       |  | (Twilio API) |  | State Machine |     |
|  | - web scrape |  | - initiate   |  | - stages      |     |
|  | - profile    |  | - hangup     |  | - transitions |     |
|  |   enrichment |  | - status     |  | - history     |     |
|  +--------------+  +--------------+  +---------------+     |
|                                                            |
|  +--------------------------------------------------+     |
|  |                Redis                              |     |
|  |  - Session state (conversation context)           |     |
|  |  - Pub/Sub (real-time events to frontend)         |     |
|  |  - Task queue (research jobs, analytics)          |     |
|  +--------------------------------------------------+     |
+------------------------------------------------------------+
```

## Conversation Flow & Persuasion Engine

State machine with the following stages:

### PRE-CALL (before dialing)
- User seeds target info (name, optional links)
- Research module enriches profile from public sources
- Supervisor selects initial persuasion approach based on profile

### INTRO
- Warm greeting, introduce self
- Build rapport using researched shared interests
- Handled primarily by Realtime model

### PITCH
- Present the pen offer, personalized based on research
- Supervisor gauges sentiment and selects pitch angle

### OBJECTION HANDLING (if hesitant)
- Address doubts, reframe value, use social proof
- Supervisor analyzes objection type and selects counter-strategy
- Can loop back to PITCH or escalate to CLOSE

### CLOSE
- Confirm the sale
- Supervisor decides if ready to close or needs more rapport

### LOGISTICS (post-close)
- Ask when and where is best for them to meet for the pen
- Confirm details

### WRAP-UP
- Thank them, end call
- Supervisor logs outcome, triggers post-call analytics

### Model Responsibility Split

| Stage | Realtime Model (voice) | Supervisor Model (text) |
|-------|----------------------|------------------------|
| Intro | Speaks greeting, small talk | -- |
| Pitch | Delivers pitch naturally | Decides which pitch angle based on profile |
| Objection | Responds conversationally | Analyzes objection type, selects counter |
| Close | Speaks the close | Decides if ready to close |
| Logistics | Asks when/where | Validates and records details |
| Wrap-up | Says goodbye | Logs outcome, triggers analytics |

### Supervisor Tools

- `lookup_profile(name)` — fetch enriched profile from research module
- `get_conversation_stage()` — current state machine position
- `transition_stage(next_stage)` — advance the conversation
- `get_objection_counters(objection_type)` — retrieve persuasion tactics
- `log_outcome(result)` — record call result

## Data Flow & Voice Pipeline

### Audio Routing

**Local (Browser) Mode:**
Browser Mic -> WebSocket -> FastAPI -> OpenAI Realtime API -> FastAPI -> WebSocket -> Browser Speaker

**Phone Call Mode:**
Student's Phone -> Twilio PSTN -> Twilio Media Stream (WSS) -> FastAPI -> OpenAI Realtime API -> FastAPI -> Twilio Media Stream (WSS) -> Twilio PSTN -> Student's Phone

**Audio format bridging:**
- Twilio sends mulaw 8kHz; OpenAI Realtime expects PCM 16-bit 24kHz
- FastAPI voice pipeline handles encoding/decoding
- Browser mode captures PCM directly via Web Audio API

### Post-Call Pipeline

Recorded audio -> Deepgram (transcription with speaker diarization) -> GPT-4.1 (analysis) -> Redis -> Next.js Dashboard

**AI analysis covers:**
- Persuasion tactic effectiveness
- Student interest peaks/drops
- Objection types and handling quality
- Overall effectiveness score
- Improvement suggestions

### Real-Time Dashboard Events (Redis Pub/Sub -> WebSocket)

- `call.started` — call initiated
- `stage.changed` — conversation stage transition
- `transcript.update` — live partial transcript
- `call.ended` — call complete, trigger analysis
- `analysis.complete` — AI analysis ready

## Distributed Systems Scaling Path

### Phase 1: Monolith (starting point)
Single FastAPI process handles everything. Redis for state + pub/sub. Handles ~1-5 concurrent calls.

### Phase 2: Worker Extraction
Extract voice pipeline into separate worker processes. FastAPI becomes orchestrator/API gateway. Workers pull call jobs from Redis task queue. Each worker handles one call. Horizontal scaling = more workers.

### Phase 3: Full Microservices
Separate services for Call Management, Research, and Analytics, communicating via Redis Streams events:
- `call.requested`
- `research.completed`
- `call.ended`
- `analysis.requested`
- `analysis.completed`

### Distributed Systems Concepts by Phase

| Phase | Concepts |
|-------|----------|
| Phase 1 | Async I/O, WebSocket management, state serialization |
| Phase 2 | Task queues, worker pools, load balancing, fault tolerance |
| Phase 3 | Service discovery, event-driven arch, eventual consistency, circuit breakers, dead letter queues, backpressure |

## Local Distributed Testing Strategy

Since we can't call real people at scale, we use **simulated callers** — GPT-4.1 instances playing the role of MIT students with varying personalities.

### Layer 1: Unit / Integration Tests (pytest)
- Test each module in isolation
- Mock OpenAI API for fast, deterministic tests
- Test stage transitions, tool calls, profile enrichment logic

### Layer 2: Simulated Call Tests
- Student Simulator: GPT-4.1 with personality prompts (easy_sell, hard_sell, busy_no_time, curious_but_broke)
- Run in text mode (skip audio) for speed and cost
- Each call produces transcript + outcome
- Assert: completion rate, stage progression, no infinite loops

### Layer 3: Distributed Load Tests (Docker Compose)
- Multiple worker containers, Redis, gateway, load tester
- Measure: calls/worker distribution, p50/p95 latency, crash recovery, queue depth, completion %
- Chaos testing: kill workers mid-call, saturate Redis, inject latency

### Observability
- Prometheus + Grafana (containerized) for metrics visualization during load tests

## Frontend Dashboard (Next.js 15)

### Pages
- `/` — Dashboard home (active calls + recent history + system metrics)
- `/calls/:id` — Single call detail (live transcript, stage indicator, profile sidebar)
- `/calls/:id/analysis` — Post-call AI analysis (transcript highlights, tactic breakdown, sentiment timeline, improvement suggestions)
- `/targets` — Target profile management (add, view research)
- `/tests` — Load test runner + distributed metrics results

### Tech
- Next.js 15 (App Router, React Server Components)
- Tailwind CSS
- WebSocket client for real-time updates
- Recharts for metrics visualization

## Project Structure

```
cord/
├── backend/                    # Python FastAPI
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── config.py           # Settings / env vars
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── calls.py    # Call CRUD + initiation
│   │   │       ├── targets.py  # Target profile management
│   │   │       └── ws.py       # WebSocket endpoints
│   │   ├── voice/
│   │   │   ├── pipeline.py     # Audio bridging (Twilio <-> OpenAI)
│   │   │   ├── realtime.py     # OpenAI Realtime API client
│   │   │   └── twilio_stream.py # Twilio Media Stream handler
│   │   ├── agent/
│   │   │   ├── supervisor.py   # GPT-4.1 supervisor logic
│   │   │   ├── state_machine.py # Conversation stages
│   │   │   ├── tools.py        # Supervisor tool definitions
│   │   │   └── prompts/        # Stage-specific prompts
│   │   ├── research/
│   │   │   ├── enricher.py     # Profile enrichment pipeline
│   │   │   └── scraper.py      # Public data scraping
│   │   ├── analytics/
│   │   │   ├── transcription.py # Deepgram integration
│   │   │   └── analyzer.py     # Post-call AI analysis
│   │   └── services/
│   │       ├── redis_client.py # Redis connection + helpers
│   │       └── call_manager.py # Twilio call lifecycle
│   ├── tests/
│   │   ├── unit/               # Module-level tests
│   │   ├── simulation/         # Simulated caller tests
│   │   └── load/               # Distributed load tests
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                   # Next.js 15
│   ├── src/app/
│   │   ├── page.tsx            # Dashboard home
│   │   ├── calls/[id]/
│   │   │   ├── page.tsx        # Call detail
│   │   │   └── analysis/page.tsx # Post-call analysis
│   │   ├── targets/page.tsx    # Target management
│   │   └── tests/page.tsx      # Load test runner
│   ├── src/components/
│   ├── src/hooks/
│   │   └── useWebSocket.ts
│   ├── src/lib/api.ts
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml          # Dev environment
├── docker-compose.test.yml     # Load testing environment
└── docs/plans/
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Voice (core) | OpenAI Realtime API (gpt-4o-mini-realtime) |
| Supervisor AI | OpenAI GPT-4.1 |
| Post-call analysis | OpenAI GPT-4.1 + Deepgram |
| Backend framework | Python FastAPI |
| Telephony | Twilio (Voice + Media Streams) |
| Message broker / state | Redis (streams, pub/sub, key-value) |
| Frontend | Next.js 15, Tailwind CSS, TypeScript |
| Real-time frontend comms | WebSocket (FastAPI -> Next.js) |
| Containerization | Docker + Docker Compose |
| Testing | pytest + simulated callers + Docker load tests |
| Observability | Prometheus + Grafana (for load testing) |
