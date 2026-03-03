# Single-Prompt Voice Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the dual-model FSM architecture with a single realtime voice model using one comprehensive prompt, removing the supervisor, state machine, and tool-call delegation.

**Architecture:** One OpenAI Realtime session with a comprehensive system prompt. No supervisor, no state machine, no tool calls. The pipeline manages session lifecycle and prompt building. Post-call analysis runs on the final transcript (unchanged).

**Tech Stack:** Python, FastAPI, OpenAI Realtime API (GA), websockets, pytest

---

### Task 1: Write the comprehensive realtime prompt

**Files:**
- Create: `backend/app/voice/prompt.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/test_prompt.py`:

```python
from app.voice.prompt import build_realtime_prompt


def test_build_prompt_includes_target_name():
    prompt = build_realtime_prompt(
        target_name="Alex Chen",
        target_profile={"name": "Alex Chen", "major": "CS", "interests": ["robotics"]},
    )
    assert "Alex Chen" in prompt


def test_build_prompt_includes_profile_details():
    prompt = build_realtime_prompt(
        target_name="Alex Chen",
        target_profile={"name": "Alex Chen", "major": "CS", "interests": ["robotics"]},
    )
    assert "CS" in prompt
    assert "robotics" in prompt


def test_build_prompt_includes_objection_guidance():
    prompt = build_realtime_prompt(
        target_name="Alex",
        target_profile={"name": "Alex"},
    )
    # Should contain objection-handling guidance
    assert "objection" in prompt.lower() or "pushback" in prompt.lower()


def test_build_prompt_includes_closing_guidance():
    prompt = build_realtime_prompt(
        target_name="Alex",
        target_profile={"name": "Alex"},
    )
    assert "close" in prompt.lower() or "wrap up" in prompt.lower() or "back off" in prompt.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.voice.prompt'`

**Step 3: Write the prompt module**

Create `backend/app/voice/prompt.py`:

```python
def build_realtime_prompt(target_name: str, target_profile: dict) -> str:
    profile_lines = "\n".join(
        f"- {k}: {v}" for k, v in target_profile.items() if v and k != "id"
    )

    return f"""You are a charming, witty person calling {target_name}, an MIT student. You're selling a pen — but make it fun and personalized. You're not a telemarketer; you're a friend-of-a-friend who happens to have an amazing pen.

## About {target_name}
{profile_lines}

## Your Personality
Confident but never pushy. Funny and relatable. Think Wolf of Wall Street energy meets your coolest friend. You genuinely enjoy talking to people and it shows.

## How to Run the Conversation

**Opening:** Start casual. Mention something specific about them (their major, interests, something you "heard about them") to build rapport. Don't pitch immediately — make them like you first.

**The pitch:** Personalize it to who they are. For an engineer, talk about precision and feel. For an artist, talk about flow and expression. For anyone — this pen has character, and so do they. Keep it light, keep it fun.

**If they push back:** Handle it naturally, don't follow a script:
- "Too expensive" → Reframe the value. Compare to what they spend on coffee. Offer to let them name their price after trying it.
- "Not interested" → Get curious about why. Create intrigue. "That's what the last person said before they bought three."
- "Too busy" → Respect it. "30 seconds — if I can't hook you by then, I'll let you go."
- "Already have a pen" → "You have A pen. But do you have THE pen?" Upgrade angle.
- "This is weird/suspicious" → Be transparent and human. "Fair — I'm literally just a person who loves this pen."

If they push back hard twice on the same thing, respect it and wrap up gracefully. Never be slimy.

**Closing:** When they seem warm, make the ask simple and direct. If they say yes, keep it brief — confirm and thank them. If they say no firmly, be gracious about it.

## Rules
- Keep every response to 1-3 sentences. This is a phone call, not a lecture.
- Be conversational. Use natural filler ("honestly," "look," "here's the thing").
- Mirror their energy — if they're joking, joke back. If they're serious, be genuine.
- Never repeat the same pitch angle twice. If one doesn't land, try a different one.
- If the conversation is clearly over (they hung up, said goodbye firmly), say goodbye warmly."""
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_prompt.py -v`
Expected: All 4 PASS

**Step 5: Commit**

```bash
cd backend && git add app/voice/prompt.py tests/unit/test_prompt.py
git commit -m "feat: add comprehensive single-prompt builder for realtime voice agent"
```

---

### Task 2: Simplify VoicePipeline — remove supervisor and state machine

**Files:**
- Modify: `backend/app/voice/pipeline.py`
- Modify: `backend/tests/unit/test_pipeline.py`

**Step 1: Write the new failing tests**

Replace contents of `backend/tests/unit/test_pipeline.py`:

```python
from unittest.mock import AsyncMock, patch

from app.voice.pipeline import VoicePipeline, CallConfig


def test_call_config_creation():
    config = CallConfig(
        call_id="call-1",
        target_name="Alex Chen",
        target_profile={"name": "Alex Chen", "major": "CS"},
    )
    assert config.call_id == "call-1"
    assert config.mode == "text"


def test_pipeline_initial_state():
    config = CallConfig(call_id="call-1", target_name="Alex", target_profile={"name": "Alex"})
    pipeline = VoicePipeline(config)
    assert pipeline.is_active is False
    assert pipeline.transcript == []


def test_pipeline_builds_prompt_with_profile():
    config = CallConfig(
        call_id="call-1",
        target_name="Alex Chen",
        target_profile={"name": "Alex Chen", "major": "CS"},
    )
    pipeline = VoicePipeline(config)
    prompt = pipeline.build_prompt()
    assert "Alex Chen" in prompt
    assert "CS" in prompt
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_pipeline.py -v`
Expected: FAIL — pipeline still imports old state_machine/supervisor

**Step 3: Rewrite pipeline.py**

Replace `backend/app/voice/pipeline.py`:

```python
import logging
from dataclasses import dataclass

from app.services.redis_client import RedisService
from app.voice.prompt import build_realtime_prompt
from app.voice.realtime import RealtimeSession, SessionConfig

logger = logging.getLogger(__name__)


@dataclass
class CallConfig:
    call_id: str
    target_name: str
    target_profile: dict
    mode: str = "text"  # "text", "browser", "twilio"


class VoicePipeline:
    def __init__(self, config: CallConfig, redis: RedisService | None = None):
        self.config = config
        self.redis = redis or RedisService()
        self.is_active = False
        self._realtime: RealtimeSession | None = None
        self._transcript: list[dict] = []

    def build_prompt(self) -> str:
        return build_realtime_prompt(
            target_name=self.config.target_name,
            target_profile=self.config.target_profile,
        )

    async def start(self) -> None:
        self.is_active = True
        await self.redis.publish_event("call.started", {
            "call_id": self.config.call_id,
            "target": self.config.target_name,
            "mode": self.config.mode,
        })

        if self.config.mode != "text":
            await self._run_voice_mode()

    async def _run_voice_mode(self) -> None:
        session_config = SessionConfig(
            instructions=self.build_prompt(),
            tools=[],
        )
        self._realtime = RealtimeSession(config=session_config)
        await self._realtime.connect()

    async def stop(self) -> None:
        self.is_active = False
        if self._realtime:
            await self._realtime.disconnect()
        await self.redis.publish_event("call.ended", {
            "call_id": self.config.call_id,
            "transcript_length": len(self._transcript),
        })

    @property
    def transcript(self) -> list[dict]:
        return list(self._transcript)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_pipeline.py -v`
Expected: All 3 PASS

**Step 5: Commit**

```bash
cd backend && git add app/voice/pipeline.py tests/unit/test_pipeline.py
git commit -m "refactor: simplify VoicePipeline, remove supervisor and state machine"
```

---

### Task 3: Simplify ws_voice.py — remove tool handling and state references

**Files:**
- Modify: `backend/app/api/routes/ws_voice.py`

**Step 1: Rewrite ws_voice.py**

Replace `backend/app/api/routes/ws_voice.py` with the simplified version. Key changes:
- Remove `from app.agent.state_machine import ConversationStage`
- Remove `delegate_to_supervisor` tool from session config
- Remove `_handle_tool_call` function entirely
- Remove all `pipeline.state_machine.current_stage.value` references
- Remove `{"type": "stage", ...}` messages to browser
- The outbound loop ignores `response.function_call_arguments.done` (no tools)

```python
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.redis_client import RedisService
from app.voice.pipeline import CallConfig, VoicePipeline
from app.voice.realtime import RealtimeSession, SessionConfig

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/voice/{call_id}")
async def voice_websocket(ws: WebSocket, call_id: str):
    """
    WebSocket endpoint bridging browser audio to OpenAI Realtime API.

    Browser sends JSON messages:
      - {"type": "start", "target_profile": {...}}
      - {"type": "audio", "audio": "<base64 PCM16 24kHz>"}
      - {"type": "text", "text": "hello"}
      - {"type": "stop"}

    Backend sends JSON messages:
      - {"type": "audio", "audio": "<base64 PCM16 24kHz>"}
      - {"type": "transcript", "role": "agent"|"user", "text": "..."}
      - {"type": "error", "message": "..."}
    """
    await ws.accept()
    redis = RedisService()
    pipeline: VoicePipeline | None = None
    realtime: RealtimeSession | None = None

    try:
        raw = await ws.receive_text()
        start_msg = json.loads(raw)

        if start_msg.get("type") != "start":
            await ws.send_json({"type": "error", "message": "First message must be type 'start'"})
            await ws.close()
            return

        target_profile = start_msg.get("target_profile", {})
        target_name = target_profile.get("name", "Unknown")

        config = CallConfig(
            call_id=call_id,
            target_name=target_name,
            target_profile=target_profile,
            mode="browser",
        )
        pipeline = VoicePipeline(config, redis=redis)
        pipeline.is_active = True

        session_config = SessionConfig(
            instructions=pipeline.build_prompt(),
            tools=[],
        )
        realtime = RealtimeSession(config=session_config)
        await realtime.connect()

        await redis.publish_event("call.started", {
            "call_id": call_id,
            "target": target_name,
            "mode": "browser",
        })

        inbound_task = asyncio.create_task(
            _inbound_loop(ws, realtime, pipeline, redis)
        )
        outbound_task = asyncio.create_task(
            _outbound_loop(ws, realtime, pipeline, redis)
        )

        done, pending = await asyncio.wait(
            [inbound_task, outbound_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        for task in done:
            if task.exception() and not isinstance(task.exception(), (WebSocketDisconnect, asyncio.CancelledError)):
                logger.error(f"Voice WS task error for {call_id}: {task.exception()}")

    except WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected: {call_id}")
    except Exception:
        logger.exception(f"Voice WebSocket error for {call_id}")
        try:
            await ws.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass
    finally:
        if realtime:
            try:
                await realtime.disconnect()
            except Exception:
                pass
        if pipeline and pipeline.is_active:
            pipeline.is_active = False
            await redis.publish_event("call.ended", {
                "call_id": call_id,
                "transcript_length": len(pipeline._transcript) if pipeline else 0,
            })


async def _inbound_loop(
    ws: WebSocket,
    realtime: RealtimeSession,
    pipeline: VoicePipeline,
    redis: RedisService,
) -> None:
    """Receive messages from the browser and forward to OpenAI Realtime API."""
    while pipeline.is_active:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "audio":
            audio_b64 = msg.get("audio", "")
            if audio_b64:
                await realtime.send_audio(audio_b64)

        elif msg_type == "text":
            text = msg.get("text", "")
            if text:
                pipeline._transcript.append({"role": "student", "content": text})
                await redis.publish_event("transcript.update", {
                    "call_id": pipeline.config.call_id,
                    "message": {"role": "user", "content": text},
                })
                await ws.send_json({"type": "transcript", "role": "user", "text": text})
                await realtime.send_text(text)

        elif msg_type == "stop":
            pipeline.is_active = False
            return

        else:
            logger.warning(f"Unknown inbound message type: {msg_type}")


async def _outbound_loop(
    ws: WebSocket,
    realtime: RealtimeSession,
    pipeline: VoicePipeline,
    redis: RedisService,
) -> None:
    """Receive events from OpenAI Realtime API and forward to the browser."""
    async for event in realtime.receive_events():
        event_type = event.get("type", "")

        if event_type == "response.output_audio.delta":
            audio_b64 = event.get("delta", "")
            if audio_b64:
                await ws.send_json({"type": "audio", "audio": audio_b64})

        elif event_type == "response.output_audio_transcript.done":
            transcript = event.get("transcript", "")
            if transcript:
                pipeline._transcript.append({"role": "agent", "content": transcript})
                await ws.send_json({"type": "transcript", "role": "agent", "text": transcript})
                await redis.publish_event("transcript.update", {
                    "call_id": pipeline.config.call_id,
                    "message": {"role": "agent", "content": transcript},
                })

        elif event_type == "conversation.item.input_audio_transcription.completed":
            user_text = event.get("transcript", "")
            if user_text:
                pipeline._transcript.append({"role": "student", "content": user_text})
                await ws.send_json({"type": "transcript", "role": "user", "text": user_text})
                await redis.publish_event("transcript.update", {
                    "call_id": pipeline.config.call_id,
                    "message": {"role": "user", "content": user_text},
                })

        elif event_type == "error":
            error_msg = event.get("error", {}).get("message", "Unknown OpenAI error")
            logger.error(f"OpenAI Realtime error for {pipeline.config.call_id}: {error_msg}")
            await ws.send_json({"type": "error", "message": error_msg})

        elif event_type in ("session.created", "session.updated", "response.done",
                            "response.output_audio_transcript.delta",
                            "input_audio_buffer.speech_started"):
            pass  # Expected events, no action needed
```

**Step 2: Run existing tests to check nothing is broken**

Run: `cd backend && python -m pytest tests/unit/test_api_calls.py -v`
Expected: PASS (calls.py will be fixed in Task 4)

**Step 3: Commit**

```bash
cd backend && git add app/api/routes/ws_voice.py
git commit -m "refactor: simplify ws_voice.py, remove tool handling and state machine refs"
```

---

### Task 4: Update calls.py — remove state machine references

**Files:**
- Modify: `backend/app/api/routes/calls.py:56-57` (send_text_message response)
- Modify: `backend/app/api/routes/calls.py:91-96` (get_call response)

**Step 1: Update calls.py**

In `send_text_message` (line 56-57), remove the `"stage"` field from the response:
```python
    return {
        "response": response,
    }
```

Note: `process_text_input` no longer exists on VoicePipeline — text mode is handled by the realtime API now. For this task, remove the text endpoint or mark it as not-yet-implemented. Since the voice pipeline is the primary flow, we'll remove the text-mode shortcut for now.

Actually, the cleaner approach: the `send_text_message` endpoint and `process_text_input` method relied on the supervisor. Since we're removing the supervisor, text mode goes through the realtime API like voice mode. Remove the `/text` endpoint and the `process_text_input` method.

In `get_call` (line 86-96), remove `"stage"`:
```python
    return {
        "call_id": call_id,
        "is_active": pipeline.is_active,
        "transcript": pipeline.transcript,
    }
```

Remove the `/text` endpoint entirely (lines 45-57).

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_api_calls.py -v`
Expected: PASS

**Step 3: Commit**

```bash
cd backend && git add app/api/routes/calls.py
git commit -m "refactor: remove state machine refs and text-mode endpoint from calls routes"
```

---

### Task 5: Delete old agent modules and their tests

**Files:**
- Delete: `backend/app/agent/state_machine.py`
- Delete: `backend/app/agent/supervisor.py`
- Delete: `backend/app/agent/tools.py`
- Delete: `backend/app/agent/prompts/system.py`
- Delete: `backend/tests/unit/test_state_machine.py`
- Delete: `backend/tests/unit/test_supervisor.py`
- Delete: `backend/tests/unit/test_tools.py`

**Step 1: Delete the files**

```bash
cd backend
rm app/agent/state_machine.py
rm app/agent/supervisor.py
rm app/agent/tools.py
rm app/agent/prompts/system.py
rm tests/unit/test_state_machine.py
rm tests/unit/test_supervisor.py
rm tests/unit/test_tools.py
```

Check if `app/agent/prompts/` directory has other files. If `system.py` was the only file, remove the `prompts/` directory too. Check if `app/agent/` has anything left worth keeping (like `__init__.py`). If the directory is empty or only has `__init__.py`, remove it.

**Step 2: Run all tests to verify nothing is broken**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All remaining tests PASS. Test count drops from ~32 to ~20ish.

**Step 3: Commit**

```bash
cd backend
git add -u  # stages deletions
git commit -m "chore: remove state machine, supervisor, tools, and their tests"
```

---

### Task 6: Run full test suite and fix any remaining import issues

**Step 1: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`

Look for any `ImportError` or `ModuleNotFoundError` referencing removed modules. Common places to check:
- `backend/app/agent/__init__.py` — may re-export removed classes
- `backend/app/main.py` — may import agent modules
- Any other route files

**Step 2: Fix any remaining broken imports**

Fix each broken import by removing the reference to deleted modules.

**Step 3: Run tests again**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASS

**Step 4: Run linter**

Run: `cd backend && ruff check app/ tests/`
Fix any issues.

**Step 5: Commit**

```bash
cd backend && git add -A && git commit -m "fix: clean up remaining imports after agent module removal"
```

---

### Task 7: Update CLAUDE.md to reflect new architecture

**Files:**
- Modify: `/CLAUDE.md`

**Step 1: Update the architecture section**

- Remove references to supervisor, state machine, 7-stage FSM, dual-model architecture
- Update the architecture diagram to show single-model flow
- Update "Key Backend Files" to remove agent/ files and add `app/voice/prompt.py`
- Update test count
- Remove `OBJECTION ↔ PITCH` state diagram

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for single-prompt architecture"
```
