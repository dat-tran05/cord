# CORD — TODO

## Rotate Credentials (DO THIS FIRST)

- [X] Rotate OpenAI API key (old one was in git history)
- [X] Rotate Twilio Account SID + Auth Token
- [X] Rotate Deepgram API key
- [X] Update `backend/.env` with new keys

## Try It Out Locally

- [ ] Start Redis: `redis-server` or `docker run -p 6379:6379 redis:7-alpine`
- [ ] Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- [ ] Start frontend: `cd frontend && npm run dev`
- [ ] Open http://localhost:3000
- [ ] Add a target on /targets (e.g., "Alex Chen", MIT, Computer Science, interests: robotics, coffee)
- [ ] Start a **text-mode** call from the dashboard — chat as the student
- [ ] Start a **voice-mode** call — speak into mic, hear the agent respond
- [ ] Try multimodal: type AND speak in the same voice call
- [ ] End the call and view the analysis at /calls/{id}/analysis

## Prompt Tuning (High Impact)

- [ ] Refine `backend/app/agent/prompts/system.py` — SUPERVISOR_SYSTEM_PROMPT
  - Adjust persuasion personality, tone, strategy preferences
  - Tune how aggressive vs. chill the agent is
  - Add/modify objection counters in OBJECTION_COUNTERS dict
- [ ] Refine `backend/app/voice/pipeline.py` — REALTIME_INSTRUCTIONS_TEMPLATE
  - This controls what the voice model says directly
  - Tune the "Wolf of Wall Street meets your cool friend" persona
  - Adjust how/when it delegates to the supervisor

## Phase 9: Twilio Phone Calls

- [ ] Create `backend/app/voice/audio.py` — mulaw (8kHz) <-> PCM16 (24kHz) conversion
- [ ] Create `backend/app/voice/twilio_stream.py` — Twilio Media Stream WebSocket handler
- [ ] Create `backend/app/api/routes/twilio_webhook.py` — POST /api/twilio/voice (returns TwiML)
- [ ] Register twilio_webhook router in `backend/app/main.py`
- [ ] Write tests for audio conversion in `backend/tests/unit/test_audio.py`
- [ ] Test with ngrok: `ngrok http 8000` and configure Twilio webhook URL

## Phase 10: Simulated Caller Tests

- [ ] Create `backend/tests/simulation/student_simulator.py` — GPT-5.2 playing MIT student
- [ ] Add personality variants: easy_sell, hard_sell, busy_no_time, curious_but_broke
- [ ] Create `backend/tests/simulation/test_simulated_call.py` — automated conversation tests
- [ ] Run: `cd backend && python -m pytest tests/simulation/ -v -s --timeout=120`

## Phase 11: Docker + Docker Compose

- [ ] Create `backend/Dockerfile`
- [ ] Create `frontend/Dockerfile`
- [ ] Create `docker-compose.yml` (dev: backend + frontend + redis)
- [ ] Create `docker-compose.test.yml` (load testing: gateway + N workers + redis + load-tester)
- [ ] Verify: `docker compose up --build`

## Phase 12: Distributed Systems Scaling

- [ ] Extract voice pipeline into separate worker process
- [ ] Implement Redis task queue for call job distribution
- [ ] Add worker health checks and crash recovery
- [ ] Load test with simulated callers across multiple workers
- [ ] Add Prometheus metrics + Grafana dashboards (optional)

## Nice-to-Haves

- [ ] Persist targets/calls to Redis instead of in-memory dicts
- [ ] Add call recording (save audio for Deepgram transcription)
- [X] ~~Add WebSocket support for browser-based voice (mic input -> OpenAI Realtime)~~
- [ ] Add call history page with filtering/sorting
- [ ] Add A/B testing for different persuasion strategies
