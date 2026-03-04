# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

CORD is a voice persuasion agent that calls MIT students and sells them a pen. It uses a **single-model architecture**: the OpenAI Realtime API (gpt-realtime-mini) handles the entire conversation autonomously -- voice synthesis, strategy, objection handling, and stage management -- guided by a comprehensive system prompt. The frontend is a Next.js dashboard for monitoring calls and viewing post-call AI analysis.

## Commands

### Backend (Python, from `backend/`)
```bash
pip install -e ".[dev]"                          # Install with dev deps
uvicorn app.main:app --reload --port 8000        # Dev server
ruff check app/                                  # Lint
ruff format app/                                 # Format
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
└── frontend/src/
    ├── app/                        # Pages: dashboard(/), targets, calls (list), calls/[id] (detail)
    ├── components/                 # VoiceChat, AnalyticsSheet, CallCard, NewCallDialog, Navbar, ui/
    ├── hooks/                      # useVoiceChat (audio bridge), useWebSocket (event stream), WebSocketProvider
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
- `app/services/handlers.py` — Registers `"enrichment"` + `"analysis"` job types; enrichment on target creation, analysis on call end
- `app/analytics/analyzer.py` — Post-call GPT analysis (effectiveness score, objection handling, sentiment arc, improvement suggestions), runs as async job via task queue

### Key Frontend Files
- `src/hooks/useVoiceChat.ts` — WebSocket to `/ws/voice/{callId}`, mic capture (ScriptProcessorNode), audio playback (AudioContext), Float32↔PCM16 conversion
- `src/lib/api.ts` — Typed fetch client (`api.targets.*`, `api.calls.*`)
- `src/components/VoiceChat.tsx` — Multimodal chat UI (voice + text in same session)
- UI uses shadcn/ui (new-york style) + Tailwind v4 + lucide-react icons, dark theme via `class="dark"` on html

### API Endpoints
- `POST/GET /api/targets`, `DELETE /api/targets/{id}` — Target CRUD (create auto-enqueues enrichment)
- `GET /api/calls` — List all calls (ordered by created_at DESC)
- `POST /api/calls` — Create call (target_id, mode: "text"|"browser"|"twilio")
- `POST /api/calls/{id}/end` — End call, save transcript, enqueue async analysis job
- `GET /api/calls/{id}/analysis` — Read-only: returns analysis or `{status: "analyzing"|"failed"|"pending"}`
- `GET /api/calls/{id}` — Get call detail (falls back to DB for historical calls)
- `WS /ws/voice/{call_id}` — Browser↔OpenAI audio bridge (JSON messages: start/audio/text/stop)
- `WS /ws/events` — Dashboard live event stream (Redis pub/sub fan-out)
- `GET /health` — Health check

## Environment

Backend requires `backend/.env` with: `OPENAI_API_KEY`, `REDIS_URL` (defaults to `redis://localhost:6379/0`). Config also includes: `OPENAI_REALTIME_MODEL` (default `gpt-realtime-mini`), `OPENAI_SUPERVISOR_MODEL` (default `gpt-5.2`, used for enrichment + analysis), `FRONTEND_URL` (default `http://localhost:3000`, used for CORS). Optional: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `DEEPGRAM_API_KEY`.

Frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`) and `NEXT_PUBLIC_WS_URL` (defaults to `ws://localhost:8000/ws/events`).

## Testing Notes

No unit tests currently (removed as irrelevant). Verify manually:
- Backend: `cd backend && python -c "from app.main import app; print('OK')"`
- Frontend: `cd frontend && npx next build` (type-checks + builds)

## Design History

Originally designed as dual-model (Realtime + GPT-5.2 supervisor with FSM). Pivoted to single-prompt architecture because the rigid state machine conflicted with natural conversation flow and the supervisor added latency. See `docs/plans/` for full design history.

## Gotchas

- Browser-mode voice calls create their pipeline locally in `ws_voice.py`, NOT in `_pipelines` dict. Any code looking up `_pipelines` must fall back to DB for browser calls.
- Transcript entries use `{role, content}` in DB but `{role, text}` in VoiceChat WebSocket messages. Use the right field for the data source.
- Backend import verification must run from `backend/` dir (needs `.env` for pydantic-settings): `cd backend && python -c "from app.main import app"`
- SQLite schema migrations need `ALTER TABLE ADD COLUMN` in try/except — table may already have the column.
- `radix-ui ^1.4.3` is monolithic: import from `radix-ui`, never `@radix-ui/*`.

## Remaining Work

See `docs/TODO.md` for phases 9-12: Twilio phone calls (audio format conversion mulaw↔PCM16), simulated caller tests (GPT-5.2 as student), Docker Compose, distributed worker scaling.
