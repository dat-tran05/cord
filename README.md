# CORD

A voice persuasion agent that calls MIT students and sells them a pen. Built with a single-model architecture using the OpenAI Realtime API for autonomous voice conversations, and a Next.js dashboard for live monitoring and post-call AI analysis.

## How It Works

```
Browser audio (PCM16 24kHz via WebSocket)
    ↓
FastAPI bridge — bidirectional async audio streaming
    ↓
OpenAI Realtime API (gpt-realtime-mini) — voice + strategy + objection handling
    ↓
Redis pub/sub — live event stream
    ↓
Next.js Dashboard — real-time call monitoring + analytics
```

The AI manages a 6-stage conversation flow entirely through a comprehensive system prompt — no external state machine or supervisor model:

`INTRO → PITCH → OBJECTION HANDLING ↔ PITCH → CLOSE → LOGISTICS → WRAP-UP`

### Target Enrichment

Before each call, targets are automatically enriched via a two-phase pipeline:
1. **Web Research** — OpenAI Responses API with `web_search_preview` finds LinkedIn, publications, projects, etc.
2. **Tactical Analysis** — GPT-5.2 produces structured talking points, rapport hooks, anticipated objections, and personalized pitch angles

### Post-Call Analytics

After each call, an async analysis job scores effectiveness, evaluates objection handling, maps sentiment arcs, and suggests improvements.

## Tech Stack

- **Backend**: Python, FastAPI, aiosqlite, Redis, OpenAI Realtime API
- **Frontend**: Next.js, TypeScript, Tailwind v4, shadcn/ui
- **Voice**: PCM16 24kHz audio streamed over WebSocket

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Redis

### Setup

```bash
# Backend
cd backend
cp .env.example .env  # Add your OPENAI_API_KEY
pip install -e ".[dev]"

# Frontend
cd frontend
npm install
```

### Run

```bash
# Start Redis
redis-server

# Backend (from backend/)
uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/)
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to access the dashboard.

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Default |
|---|---|---|
| `OPENAI_API_KEY` | Yes | — |
| `REDIS_URL` | No | `redis://localhost:6379/0` |
| `OPENAI_REALTIME_MODEL` | No | `gpt-realtime-mini` |
| `OPENAI_SUPERVISOR_MODEL` | No | `gpt-5.2` |
| `FRONTEND_URL` | No | `http://localhost:3000` |
| `TWILIO_ACCOUNT_SID` | No | — |
| `TWILIO_AUTH_TOKEN` | No | — |
| `DEEPGRAM_API_KEY` | No | — |

### Frontend

| Variable | Default |
|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws/events` |

## Project Structure

```
cord/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app + lifespan
│       ├── voice/               # Realtime API pipeline + prompt builder
│       ├── api/routes/          # REST + WebSocket endpoints
│       ├── research/            # Two-phase target enrichment
│       ├── analytics/           # Post-call AI analysis
│       └── services/            # Redis client + async task queue
└── frontend/src/
    ├── app/                     # Pages: dashboard, targets, calls
    ├── components/              # VoiceChat, analytics, call cards
    ├── hooks/                   # Audio bridge, WebSocket event stream
    └── lib/                     # Typed API client
```
