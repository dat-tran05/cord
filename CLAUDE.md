# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

CORD is a voice persuasion agent that calls MIT students and sells them a pen. It uses a **dual-model architecture**: OpenAI Realtime API (gpt-realtime-mini) handles natural voice conversation while a GPT-5.2 supervisor makes strategic decisions via tool calls. The frontend is a Next.js dashboard for monitoring calls and viewing post-call AI analysis.

## Commands

### Backend (Python, from `backend/`)
```bash
pip install -e ".[dev]"                          # Install with dev deps
uvicorn app.main:app --reload --port 8000        # Dev server
pytest tests/ -v                                 # All tests (32 total)
pytest tests/unit/test_state_machine.py -v       # Single file
pytest tests/unit/test_supervisor.py::test_lookup_profile -v  # Single test
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

### Dual-Model Voice Pipeline
```
Browser audio (PCM16 24kHz via WebSocket)
    ↓
ws_voice.py — bidirectional bridge with two async loops (inbound/outbound)
    ↓
OpenAI Realtime API (gpt-realtime-mini) — natural conversation + voice synthesis
    ↓ delegates via "delegate_to_supervisor" tool call
Supervisor (GPT-5.2) — strategy, stage transitions, objection counters
    ↓
Redis — session state (cord:session:*) + pub/sub events (cord:events)
    ↓
Next.js Dashboard — live event stream via /ws/events
```

### Conversation State Machine (7 stages)
`PRE_CALL → INTRO → PITCH → OBJECTION ↔ PITCH → CLOSE → LOGISTICS → WRAP_UP`

OBJECTION can loop back to PITCH. Transitions are validated by `state_machine.py`.

### OpenAI Realtime API (GA, not Beta)
The API uses the **GA format** which differs from beta docs you may find online:
- `format` is an **object** `{"type": "audio/pcm", "rate": 24000}`, not a string
- `output_modalities` must be `["audio"]` OR `["text"]`, cannot request both
- Tools use **flat format**: `{"type": "function", "name": "...", "parameters": {...}}` (NOT the nested `"function": {...}` wrapper that Chat Completions uses)
- Event names: `response.output_audio.delta` (not `response.audio.delta`), `response.output_audio_transcript.delta/done`
- Session config requires `"type": "realtime"` at session level

### Key Backend Files
- `app/voice/realtime.py` — SessionConfig + RealtimeSession WebSocket client
- `app/voice/pipeline.py` — VoicePipeline orchestrator, builds realtime instructions
- `app/api/routes/ws_voice.py` — Browser↔OpenAI bridge (inbound + outbound async loops)
- `app/agent/supervisor.py` — GPT-5.2 with tool-calling loop
- `app/agent/state_machine.py` — ConversationStage enum + FSM with validation
- `app/agent/tools.py` — 4 supervisor tools: lookup_profile, transition_stage, get_objection_counters, log_outcome
- `app/agent/prompts/system.py` — SUPERVISOR_SYSTEM_PROMPT template + OBJECTION_COUNTERS dict

### Key Frontend Files
- `src/hooks/useVoiceChat.ts` — WebSocket to `/ws/voice/{callId}`, mic capture (ScriptProcessorNode), audio playback (AudioContext), Float32↔PCM16 conversion
- `src/lib/api.ts` — Typed fetch client (`api.targets.*`, `api.calls.*`)
- `src/components/VoiceChat.tsx` — Multimodal chat UI (voice + text in same session)
- UI uses shadcn/ui (new-york style) + Tailwind v4 + lucide-react icons, dark theme via `class="dark"` on html

### API Endpoints
- REST: `/api/targets` (CRUD), `/api/calls` (create/get/text/end/analysis)
- WebSocket: `/ws/voice/{call_id}` (audio bridge), `/ws/events` (dashboard event stream)

## Environment

Backend requires `backend/.env` with: `OPENAI_API_KEY`, `REDIS_URL` (defaults to localhost:6379). Optional: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `DEEPGRAM_API_KEY`.

Frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

## Testing Notes

All 32 unit tests use mocks (no real API calls). Tests in `backend/tests/unit/` cover: state machine transitions, supervisor tool handling, pipeline config, realtime session formatting, Redis client, API routes, analyzer, enricher, tool schemas.

The `test_api_calls.py` uses an autouse fixture to clear module-level `_targets` and `_pipelines` dicts between tests to prevent state pollution.

## Remaining Work

See `docs/TODO.md` for phases 9-12: Twilio phone calls (audio format conversion mulaw↔PCM16), simulated caller tests (GPT-5.2 as student), Docker Compose, distributed worker scaling.
