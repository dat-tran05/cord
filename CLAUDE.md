# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

CORD is a voice persuasion agent that calls MIT students and sells them a pen. It uses a **single-model architecture**: the OpenAI Realtime API (gpt-realtime-mini) handles the entire conversation autonomously -- voice synthesis, strategy, objection handling, and stage management -- guided by a comprehensive system prompt. The frontend is a Next.js dashboard for monitoring calls and viewing post-call AI analysis.

## Commands

### Backend (Python, from `backend/`)
```bash
pip install -e ".[dev]"                          # Install with dev deps
uvicorn app.main:app --reload --port 8000        # Dev server
pytest tests/ -v                                 # All tests (40 total)
pytest tests/unit/test_pipeline.py -v            # Single file
pytest tests/unit/test_prompt.py::TestBuildRealtimePrompt::test_includes_target_name -v  # Single test
ruff check app/ tests/                           # Lint
ruff format app/ tests/                          # Format
```

### Frontend (TypeScript, from `frontend/`)
```bash
npm install                     # Install deps
npm run dev                     # Dev server on :3000
npx next build                  # Production build (also checks types)
npm run lint                    # ESLint
```

### Full stack local dev
```bash
redis-server                    # or: docker run -p 6379:6379 redis:7-alpine
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Architecture

### Project Structure
```
cord/
├── CLAUDE.md
├── docs/                          # Design docs, TODO, plans
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI + lifespan (DB init, worker start, crash recovery)
│   │   ├── config.py              # pydantic-settings env config
│   │   ├── db.py                  # aiosqlite — targets + calls tables
│   │   ├── voice/                 # Voice pipeline
│   │   │   ├── prompt.py          # build_realtime_prompt()
│   │   │   ├── pipeline.py        # VoicePipeline + CallConfig
│   │   │   └── realtime.py        # RealtimeSession (OpenAI WS client)
│   │   ├── api/routes/            # REST + WebSocket handlers
│   │   │   ├── calls.py, targets.py, ws.py, ws_voice.py
│   │   ├── research/enricher.py   # Two-phase target enrichment (web search → tactical analysis)
│   │   ├── analytics/             # Post-call analyzer + Deepgram transcription
│   │   └── services/              # Redis client, task queue, job handlers
│   └── tests/unit/                # 8 files, 40 tests
└── frontend/src/
    ├── app/                        # Pages: dashboard(/), targets, calls/[id], analysis
    ├── components/                 # VoiceChat, CallCard, NewCallDialog, Navbar, ui/
    ├── hooks/                      # useVoiceChat (audio bridge), useWebSocket (event stream)
    └── lib/                        # api.ts (typed REST client), utils.ts
```

### Single-Model Voice Pipeline
```
Browser audio (PCM16 24kHz via WebSocket)
    ↓
ws_voice.py — bidirectional bridge with two async loops (inbound/outbound)
    ↓
OpenAI Realtime API (gpt-realtime-mini) — full conversation (voice + strategy)
    ↓
Redis — pub/sub events (cord:events)
    ↓
Next.js Dashboard — live event stream via /ws/events
```

### Conversation Flow (6 stages, managed by the prompt)
`INTRO → PITCH → OBJECTION HANDLING ↔ PITCH → CLOSE → LOGISTICS → WRAP-UP`

The Realtime model manages stage transitions autonomously via a comprehensive system prompt that includes all strategy, objection counters, and conversation flow guidance. No external state machine or supervisor model.

### OpenAI Realtime API (GA, not Beta)
The API uses the **GA format** which differs from beta docs you may find online:
- `format` is an **object** `{"type": "audio/pcm", "rate": 24000}`, not a string
- `output_modalities` must be `["audio"]` OR `["text"]`, cannot request both
- No tools are registered -- the model runs autonomously via a detailed system prompt
- Event names: `response.output_audio.delta` (not `response.audio.delta`), `response.output_audio_transcript.delta/done`
- Session config requires `"type": "realtime"` at session level

### Key Backend Files
- `app/voice/prompt.py` — System prompt builder (target profile, enriched data, objection counters, conversation flow)
- `app/voice/realtime.py` — SessionConfig + RealtimeSession WebSocket client (GA format)
- `app/voice/pipeline.py` — VoicePipeline orchestrator, builds prompt and manages session lifecycle
- `app/api/routes/ws_voice.py` — Browser↔OpenAI bridge (inbound + outbound async loops)
- `app/db.py` — aiosqlite layer: `targets` table (with enrichment_status, enriched_profile JSON) + `calls` table (with transcript JSON, analysis JSON)
- `app/research/enricher.py` — Two-phase enrichment: web research (Responses API + web_search_preview) → tactical analysis (Chat Completions + structured JSON schema via gpt-5.2)
- `app/services/task_queue.py` — Redis-backed async job queue with crash recovery (pending→processing→completed, re-enqueues on startup)
- `app/services/handlers.py` — Registers `"enrichment"` job type; auto-enqueued on target creation
- `app/analytics/analyzer.py` — Post-call GPT analysis (effectiveness score, objection handling, sentiment arc, improvement suggestions)

### Key Frontend Files
- `src/hooks/useVoiceChat.ts` — WebSocket to `/ws/voice/{callId}`, mic capture (ScriptProcessorNode), audio playback (AudioContext), Float32↔PCM16 conversion
- `src/lib/api.ts` — Typed fetch client (`api.targets.*`, `api.calls.*`)
- `src/components/VoiceChat.tsx` — Multimodal chat UI (voice + text in same session)
- UI uses shadcn/ui (new-york style) + Tailwind v4 + lucide-react icons, dark theme via `class="dark"` on html

### API Endpoints
- `POST/GET /api/targets`, `DELETE /api/targets/{id}` — Target CRUD (create auto-enqueues enrichment)
- `POST /api/calls` — Create call (target_id, mode: "text"|"browser"|"twilio")
- `POST /api/calls/{id}/end` — End call, save transcript
- `GET /api/calls/{id}/analysis` — Run/fetch GPT analysis on transcript
- `GET /api/calls/{id}` — Get active call state
- `WS /ws/voice/{call_id}` — Browser↔OpenAI audio bridge (JSON messages: start/audio/text/stop)
- `WS /ws/events` — Dashboard live event stream (Redis pub/sub fan-out)
- `GET /health` — Health check

## Environment

Backend requires `backend/.env` with: `OPENAI_API_KEY`, `REDIS_URL` (defaults to `redis://localhost:6379/0`). Config also includes: `OPENAI_REALTIME_MODEL` (default `gpt-realtime-mini`), `OPENAI_SUPERVISOR_MODEL` (default `gpt-5.2`, used for enrichment + analysis), `FRONTEND_URL` (default `http://localhost:3000`, used for CORS). Optional: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `DEEPGRAM_API_KEY`.

Frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`) and `NEXT_PUBLIC_WS_URL` (defaults to `ws://localhost:8000/ws/events`).

## Testing Notes

All 40 unit tests use mocks (no real API calls). Tests in `backend/tests/unit/` cover: prompt builder, pipeline config/lifecycle, realtime session formatting, Redis client, API routes, analyzer, enricher, enrichment flow.
- Redis tests use `fakeredis.FakeAsyncRedis`
- DB tests use `aiosqlite` with `":memory:"`
- API integration tests use `httpx.AsyncClient` with `ASGITransport`
- Enrichment flow tests verify status transitions: `pending → enriching → enriched/failed`

## Design History

Originally designed as dual-model (Realtime + GPT-5.2 supervisor with FSM). Pivoted to single-prompt architecture because the rigid state machine conflicted with natural conversation flow and the supervisor added latency. See `docs/plans/` for full design history.

## Remaining Work

See `docs/TODO.md` for phases 9-12: Twilio phone calls (audio format conversion mulaw↔PCM16), simulated caller tests (GPT-5.2 as student), Docker Compose, distributed worker scaling.
