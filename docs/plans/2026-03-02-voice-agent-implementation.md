# CORD Voice Persuasion Agent — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a voice persuasion agent that calls MIT students to sell a pen, with a Next.js dashboard and progressive distributed systems architecture.

**Architecture:** Chat-Supervisor modular monolith — OpenAI Realtime API (voice) + GPT-5.2 (supervisor) — FastAPI backend, Next.js 15 frontend, Redis state, Twilio telephony, Deepgram transcription.

**Tech Stack:** Python 3.12+, FastAPI, OpenAI SDK, Twilio, Deepgram, Redis, Next.js 15, Tailwind CSS, Docker

---

## Phase 1: Project Scaffolding & Core Infrastructure

### Task 1: Python Backend Setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/unit/__init__.py`

**Step 1: Create pyproject.toml with all dependencies**

```toml
[project]
name = "cord-backend"
version = "0.1.0"
description = "CORD Voice Persuasion Agent Backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "openai>=1.50.0",
    "redis[hiredis]>=5.0.0",
    "twilio>=9.0.0",
    "deepgram-sdk>=3.5.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "websockets>=12.0",
    "httpx>=0.27.0",
    "audioop-lts>=0.2.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.0",
    "fakeredis>=2.25.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

**Step 2: Create config module**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_realtime_model: str = "gpt-realtime-mini"
    openai_supervisor_model: str = "gpt-5.2"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Deepgram
    deepgram_api_key: str = ""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

**Step 3: Create minimal FastAPI app**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="CORD Voice Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Create empty `__init__.py` files**

Create `backend/app/__init__.py`, `backend/tests/__init__.py`, `backend/tests/unit/__init__.py` as empty files.

**Step 5: Create `.env.example`**

```env
OPENAI_API_KEY=sk-...
REDIS_URL=redis://localhost:6379/0
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
DEEPGRAM_API_KEY=
```

**Step 6: Install and verify**

Run:
```bash
cd backend && pip install -e ".[dev]"
```

Run:
```bash
cd backend && uvicorn app.main:app --reload --port 8000 &
curl http://localhost:8000/health
```
Expected: `{"status":"ok"}`

**Step 7: Commit**

```bash
git add backend/ .env.example
git commit -m "feat: scaffold backend with FastAPI, config, and dependencies"
```

---

### Task 2: Redis Client Module

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/redis_client.py`
- Test: `backend/tests/unit/test_redis_client.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_redis_client.py
import pytest
from fakeredis import aioFakeRedis

from app.services.redis_client import RedisService


@pytest.fixture
async def redis_service():
    fake_redis = aioFakeRedis()
    service = RedisService(client=fake_redis)
    yield service
    await fake_redis.aclose()


async def test_set_and_get_session(redis_service: RedisService):
    await redis_service.set_session("call-1", {"stage": "intro", "target": "Alex"})
    session = await redis_service.get_session("call-1")
    assert session["stage"] == "intro"
    assert session["target"] == "Alex"


async def test_get_nonexistent_session(redis_service: RedisService):
    session = await redis_service.get_session("nonexistent")
    assert session is None


async def test_publish_event(redis_service: RedisService):
    # Just ensure it doesn't raise
    await redis_service.publish_event("call.started", {"call_id": "call-1"})


async def test_delete_session(redis_service: RedisService):
    await redis_service.set_session("call-1", {"stage": "intro"})
    await redis_service.delete_session("call-1")
    session = await redis_service.get_session("call-1")
    assert session is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_redis_client.py -v`
Expected: FAIL (import error)

**Step 3: Implement RedisService**

```python
# backend/app/services/redis_client.py
import json

from redis.asyncio import Redis

from app.config import settings

SESSION_PREFIX = "cord:session:"
EVENT_CHANNEL = "cord:events"
SESSION_TTL = 3600  # 1 hour


class RedisService:
    def __init__(self, client: Redis | None = None):
        self._client = client

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    async def set_session(self, call_id: str, data: dict) -> None:
        key = f"{SESSION_PREFIX}{call_id}"
        await self.client.set(key, json.dumps(data), ex=SESSION_TTL)

    async def get_session(self, call_id: str) -> dict | None:
        key = f"{SESSION_PREFIX}{call_id}"
        raw = await self.client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def delete_session(self, call_id: str) -> None:
        key = f"{SESSION_PREFIX}{call_id}"
        await self.client.delete(key)

    async def publish_event(self, event_type: str, data: dict) -> None:
        payload = json.dumps({"event": event_type, **data})
        await self.client.publish(EVENT_CHANNEL, payload)
```

Create empty `backend/app/services/__init__.py`.

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_redis_client.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/ backend/tests/unit/test_redis_client.py
git commit -m "feat: add Redis service with session and pub/sub support"
```

---

## Phase 2: Conversation State Machine

### Task 3: State Machine

**Files:**
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/state_machine.py`
- Test: `backend/tests/unit/test_state_machine.py`

**Step 1: Write failing tests**

```python
# backend/tests/unit/test_state_machine.py
import pytest

from app.agent.state_machine import ConversationStage, ConversationStateMachine


def test_initial_stage_is_pre_call():
    sm = ConversationStateMachine()
    assert sm.current_stage == ConversationStage.PRE_CALL


def test_valid_transition_pre_call_to_intro():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    assert sm.current_stage == ConversationStage.INTRO


def test_invalid_transition_raises():
    sm = ConversationStateMachine()
    with pytest.raises(ValueError, match="Invalid transition"):
        sm.transition(ConversationStage.CLOSE)


def test_full_happy_path():
    sm = ConversationStateMachine()
    for stage in [
        ConversationStage.INTRO,
        ConversationStage.PITCH,
        ConversationStage.CLOSE,
        ConversationStage.LOGISTICS,
        ConversationStage.WRAP_UP,
    ]:
        sm.transition(stage)
    assert sm.current_stage == ConversationStage.WRAP_UP


def test_objection_loop_back_to_pitch():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    sm.transition(ConversationStage.PITCH)
    sm.transition(ConversationStage.OBJECTION)
    sm.transition(ConversationStage.PITCH)
    assert sm.current_stage == ConversationStage.PITCH


def test_history_tracks_transitions():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    sm.transition(ConversationStage.PITCH)
    assert sm.history == [ConversationStage.PRE_CALL, ConversationStage.INTRO, ConversationStage.PITCH]


def test_to_dict_and_from_dict():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    data = sm.to_dict()
    restored = ConversationStateMachine.from_dict(data)
    assert restored.current_stage == ConversationStage.INTRO
    assert restored.history == sm.history
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_state_machine.py -v`
Expected: FAIL (import error)

**Step 3: Implement state machine**

```python
# backend/app/agent/state_machine.py
from enum import StrEnum


class ConversationStage(StrEnum):
    PRE_CALL = "pre_call"
    INTRO = "intro"
    PITCH = "pitch"
    OBJECTION = "objection"
    CLOSE = "close"
    LOGISTICS = "logistics"
    WRAP_UP = "wrap_up"


# Adjacency list: from_stage -> set of valid next stages
VALID_TRANSITIONS: dict[ConversationStage, set[ConversationStage]] = {
    ConversationStage.PRE_CALL: {ConversationStage.INTRO},
    ConversationStage.INTRO: {ConversationStage.PITCH},
    ConversationStage.PITCH: {ConversationStage.OBJECTION, ConversationStage.CLOSE},
    ConversationStage.OBJECTION: {ConversationStage.PITCH, ConversationStage.CLOSE},
    ConversationStage.CLOSE: {ConversationStage.LOGISTICS, ConversationStage.WRAP_UP},
    ConversationStage.LOGISTICS: {ConversationStage.WRAP_UP},
    ConversationStage.WRAP_UP: set(),
}


class ConversationStateMachine:
    def __init__(self, stage: ConversationStage = ConversationStage.PRE_CALL):
        self._stage = stage
        self._history: list[ConversationStage] = [stage]

    @property
    def current_stage(self) -> ConversationStage:
        return self._stage

    @property
    def history(self) -> list[ConversationStage]:
        return list(self._history)

    def transition(self, next_stage: ConversationStage) -> None:
        valid = VALID_TRANSITIONS.get(self._stage, set())
        if next_stage not in valid:
            raise ValueError(
                f"Invalid transition from {self._stage} to {next_stage}. "
                f"Valid: {valid}"
            )
        self._stage = next_stage
        self._history.append(next_stage)

    def to_dict(self) -> dict:
        return {
            "stage": self._stage.value,
            "history": [s.value for s in self._history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationStateMachine":
        sm = cls(stage=ConversationStage(data["stage"]))
        sm._history = [ConversationStage(s) for s in data["history"]]
        return sm
```

Create empty `backend/app/agent/__init__.py`.

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_state_machine.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/app/agent/ backend/tests/unit/test_state_machine.py
git commit -m "feat: add conversation state machine with stage transitions"
```

---

## Phase 3: Supervisor Agent (GPT-5.2)

### Task 4: Supervisor Tool Definitions

**Files:**
- Create: `backend/app/agent/tools.py`
- Test: `backend/tests/unit/test_tools.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_tools.py
from app.agent.tools import SUPERVISOR_TOOLS, get_tool_schemas


def test_tool_schemas_are_valid_openai_format():
    schemas = get_tool_schemas()
    assert isinstance(schemas, list)
    assert len(schemas) > 0
    for schema in schemas:
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_all_expected_tools_present():
    names = {t["function"]["name"] for t in get_tool_schemas()}
    expected = {"lookup_profile", "transition_stage", "get_objection_counters", "log_outcome"}
    assert expected.issubset(names)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_tools.py -v`
Expected: FAIL (import error)

**Step 3: Implement tool definitions**

```python
# backend/app/agent/tools.py

SUPERVISOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_profile",
            "description": "Fetch the enriched profile for the target person. Returns their name, interests, major, and any other public info gathered during pre-call research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the target person"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transition_stage",
            "description": "Advance the conversation to a new stage. Valid stages: intro, pitch, objection, close, logistics, wrap_up. Only valid transitions are allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "next_stage": {
                        "type": "string",
                        "enum": ["intro", "pitch", "objection", "close", "logistics", "wrap_up"],
                        "description": "The stage to transition to",
                    },
                },
                "required": ["next_stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_objection_counters",
            "description": "Get persuasion tactics to counter a specific type of objection from the target.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objection_type": {
                        "type": "string",
                        "enum": ["too_expensive", "not_interested", "too_busy", "already_have_one", "suspicious"],
                        "description": "The type of objection raised",
                    },
                },
                "required": ["objection_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_outcome",
            "description": "Record the final outcome of the call after wrap-up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "enum": ["sold", "rejected", "callback_requested", "no_answer", "hung_up"],
                        "description": "The outcome of the call",
                    },
                    "notes": {"type": "string", "description": "Any additional notes about the call"},
                },
                "required": ["result"],
            },
        },
    },
]


def get_tool_schemas() -> list[dict]:
    return SUPERVISOR_TOOLS
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_tools.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add backend/app/agent/tools.py backend/tests/unit/test_tools.py
git commit -m "feat: add supervisor tool definitions for OpenAI function calling"
```

---

### Task 5: Supervisor Agent Integration

**Files:**
- Create: `backend/app/agent/prompts/` (directory)
- Create: `backend/app/agent/prompts/system.py`
- Create: `backend/app/agent/supervisor.py`
- Test: `backend/tests/unit/test_supervisor.py`

**Step 1: Write the system prompts**

```python
# backend/app/agent/prompts/system.py

SUPERVISOR_SYSTEM_PROMPT = """You are the strategic brain behind a persuasion agent selling a pen to an MIT student.

Your role:
- Decide WHAT to say (strategy), not HOW to say it (that's the voice model's job)
- Analyze the student's responses for sentiment and objections
- Choose the right persuasion approach based on their profile
- Decide when to transition between conversation stages

Current target profile:
{profile}

Current conversation stage: {stage}
Conversation history summary: {history_summary}

Guidelines:
- Be charming and relatable, never pushy or aggressive
- Use the target's interests and background to personalize the pitch
- If they object, address it genuinely — don't be slimy
- Know when to back off — if they're firm, respect it and wrap up gracefully
- The pen is special because YOU are selling it — channel Wolf of Wall Street energy but keep it fun

When you need to take action, use the available tools.
When you want the voice model to say something specific, return it as your response text.
"""

OBJECTION_COUNTERS = {
    "too_expensive": [
        "Reframe as investment: 'This pen has written ideas worth millions — what if your next big idea flows through it?'",
        "Compare to daily spending: 'You probably spent more on coffee today. This pen lasts forever.'",
        "Offer payment flexibility: 'Tell you what — pay me what you think it's worth after using it for a week.'",
    ],
    "not_interested": [
        "Create curiosity: 'That's exactly what the last person said before they bought three.'",
        "Appeal to their field: 'As a {major} student, don't you want something that feels intentional when you write?'",
        "Social proof: 'I sold one to someone in your dorm last week — they texted me to say thanks.'",
    ],
    "too_busy": [
        "Respect their time: 'I get it, 30 seconds — if I can't convince you by then, I'll walk away.'",
        "Create urgency: 'Perfect timing actually — I only have one left and I'm heading out.'",
    ],
    "already_have_one": [
        "Differentiate: 'You have A pen. But do you have THE pen? This one is different.'",
        "Upgrade angle: 'Great taste! But imagine upgrading — like going from dining hall coffee to Blue Bottle.'",
    ],
    "suspicious": [
        "Be transparent: 'Fair — I'm literally just a guy who loves this pen and wants to share the love.'",
        "Build trust: 'Try it first. Write your name. If you don't feel the difference, no sale.'",
    ],
}
```

Create empty `backend/app/agent/prompts/__init__.py`.

**Step 2: Write failing test**

```python
# backend/tests/unit/test_supervisor.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.supervisor import Supervisor
from app.agent.state_machine import ConversationStage


@pytest.fixture
def supervisor():
    return Supervisor(
        target_profile={"name": "Alex Chen", "major": "Computer Science", "interests": ["robotics", "coffee"]},
    )


def test_supervisor_builds_system_prompt(supervisor: Supervisor):
    prompt = supervisor._build_system_prompt()
    assert "Alex Chen" in prompt
    assert "Computer Science" in prompt


def test_get_objection_counters(supervisor: Supervisor):
    counters = supervisor.handle_tool_call("get_objection_counters", {"objection_type": "too_expensive"})
    assert isinstance(counters, list)
    assert len(counters) > 0


def test_transition_stage(supervisor: Supervisor):
    supervisor.state_machine.transition(ConversationStage.INTRO)
    result = supervisor.handle_tool_call("transition_stage", {"next_stage": "pitch"})
    assert supervisor.state_machine.current_stage == ConversationStage.PITCH
    assert "pitch" in result.lower()


def test_transition_stage_invalid(supervisor: Supervisor):
    result = supervisor.handle_tool_call("transition_stage", {"next_stage": "close"})
    assert "invalid" in result.lower() or "error" in result.lower()


def test_lookup_profile(supervisor: Supervisor):
    result = supervisor.handle_tool_call("lookup_profile", {"name": "Alex Chen"})
    assert "Alex Chen" in result
    assert "Computer Science" in result
```

**Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_supervisor.py -v`
Expected: FAIL (import error)

**Step 4: Implement Supervisor**

```python
# backend/app/agent/supervisor.py
import json

from openai import AsyncOpenAI

from app.agent.prompts.system import OBJECTION_COUNTERS, SUPERVISOR_SYSTEM_PROMPT
from app.agent.state_machine import ConversationStage, ConversationStateMachine
from app.agent.tools import get_tool_schemas
from app.config import settings


class Supervisor:
    def __init__(self, target_profile: dict, state_machine: ConversationStateMachine | None = None):
        self.target_profile = target_profile
        self.state_machine = state_machine or ConversationStateMachine()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._messages: list[dict] = []

    def _build_system_prompt(self) -> str:
        return SUPERVISOR_SYSTEM_PROMPT.format(
            profile=json.dumps(self.target_profile, indent=2),
            stage=self.state_machine.current_stage.value,
            history_summary=", ".join(s.value for s in self.state_machine.history),
        )

    def handle_tool_call(self, tool_name: str, args: dict) -> str:
        if tool_name == "lookup_profile":
            return json.dumps(self.target_profile, indent=2)

        if tool_name == "transition_stage":
            try:
                next_stage = ConversationStage(args["next_stage"])
                self.state_machine.transition(next_stage)
                return f"Transitioned to {next_stage.value}"
            except ValueError as e:
                return f"Error: {e}"

        if tool_name == "get_objection_counters":
            objection_type = args["objection_type"]
            counters = OBJECTION_COUNTERS.get(objection_type, ["Acknowledge their concern and try a different angle."])
            return json.dumps(counters)

        if tool_name == "log_outcome":
            return f"Outcome logged: {args['result']}"

        return f"Unknown tool: {tool_name}"

    async def get_response(self, user_message: str) -> str:
        self._messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model=settings.openai_supervisor_model,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                *self._messages,
            ],
            tools=get_tool_schemas(),
        )

        message = response.choices[0].message

        # Handle tool calls
        while message.tool_calls:
            self._messages.append(message.model_dump())
            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = self.handle_tool_call(tool_call.function.name, args)
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            response = await self._client.chat.completions.create(
                model=settings.openai_supervisor_model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    *self._messages,
                ],
                tools=get_tool_schemas(),
            )
            message = response.choices[0].message

        assistant_text = message.content or ""
        self._messages.append({"role": "assistant", "content": assistant_text})
        return assistant_text
```

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_supervisor.py -v`
Expected: All 5 tests PASS (sync tool call tests don't need API)

**Step 6: Commit**

```bash
git add backend/app/agent/prompts/ backend/app/agent/supervisor.py backend/tests/unit/test_supervisor.py
git commit -m "feat: add supervisor agent with tool handling and GPT-5.2 integration"
```

---

## Phase 4: Research Module

### Task 6: Profile Enrichment

**Files:**
- Create: `backend/app/research/__init__.py`
- Create: `backend/app/research/enricher.py`
- Test: `backend/tests/unit/test_enricher.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_enricher.py
import pytest
from unittest.mock import AsyncMock, patch

from app.research.enricher import ProfileEnricher, TargetProfile


def test_target_profile_from_seed():
    profile = TargetProfile(name="Alex Chen", school="MIT")
    assert profile.name == "Alex Chen"
    assert profile.school == "MIT"
    assert profile.interests == []


def test_target_profile_to_dict():
    profile = TargetProfile(
        name="Alex Chen",
        school="MIT",
        major="Computer Science",
        interests=["robotics", "coffee"],
    )
    d = profile.to_dict()
    assert d["name"] == "Alex Chen"
    assert d["major"] == "Computer Science"


async def test_enrich_with_user_provided_data():
    enricher = ProfileEnricher()
    profile = await enricher.enrich(
        name="Alex Chen",
        seed_data={"school": "MIT", "major": "CS", "interests": ["robotics"]},
    )
    assert profile.name == "Alex Chen"
    assert profile.major == "CS"
    assert "robotics" in profile.interests
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_enricher.py -v`
Expected: FAIL (import error)

**Step 3: Implement enricher**

```python
# backend/app/research/enricher.py
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import settings


@dataclass
class TargetProfile:
    name: str
    school: str = ""
    major: str = ""
    year: str = ""
    interests: list[str] = field(default_factory=list)
    clubs: list[str] = field(default_factory=list)
    bio: str = ""
    enrichment_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "school": self.school,
            "major": self.major,
            "year": self.year,
            "interests": self.interests,
            "clubs": self.clubs,
            "bio": self.bio,
            "enrichment_notes": self.enrichment_notes,
        }


class ProfileEnricher:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def enrich(self, name: str, seed_data: dict | None = None) -> TargetProfile:
        profile = TargetProfile(name=name)

        if seed_data:
            profile.school = seed_data.get("school", profile.school)
            profile.major = seed_data.get("major", profile.major)
            profile.year = seed_data.get("year", profile.year)
            profile.interests = seed_data.get("interests", profile.interests)
            profile.clubs = seed_data.get("clubs", profile.clubs)
            profile.bio = seed_data.get("bio", profile.bio)

        # Auto-enrich using GPT to generate plausible talking points
        if profile.school or profile.major:
            profile.enrichment_notes = await self._generate_talking_points(profile)

        return profile

    async def _generate_talking_points(self, profile: TargetProfile) -> str:
        prompt = (
            f"Given this person's profile, generate 3-5 brief talking points I could use "
            f"to build rapport with them in a casual conversation. Be specific and creative.\n\n"
            f"Name: {profile.name}\n"
            f"School: {profile.school}\n"
            f"Major: {profile.major}\n"
            f"Interests: {', '.join(profile.interests)}\n"
            f"Clubs: {', '.join(profile.clubs)}\n"
        )
        response = await self._client.chat.completions.create(
            model=settings.openai_supervisor_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
```

Create empty `backend/app/research/__init__.py`.

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_enricher.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/app/research/ backend/tests/unit/test_enricher.py
git commit -m "feat: add profile enricher with seed data and GPT talking points"
```

---

## Phase 5: Voice Pipeline (OpenAI Realtime API)

### Task 7: OpenAI Realtime WebSocket Client

**Files:**
- Create: `backend/app/voice/__init__.py`
- Create: `backend/app/voice/realtime.py`
- Test: `backend/tests/unit/test_realtime.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_realtime.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.voice.realtime import RealtimeSession, SessionConfig


def test_session_config_defaults():
    config = SessionConfig(instructions="Sell a pen")
    assert config.voice == "alloy"
    assert config.model == "gpt-realtime-mini"


def test_session_config_to_event():
    config = SessionConfig(instructions="Sell a pen", tools=[{"type": "function", "name": "test"}])
    event = config.to_session_update_event()
    assert event["type"] == "session.update"
    assert event["session"]["instructions"] == "Sell a pen"
    assert event["session"]["voice"] == "alloy"
    assert len(event["session"]["tools"]) == 1


def test_create_audio_append_event():
    event = RealtimeSession.create_audio_append_event("dGVzdA==")
    assert event["type"] == "input_audio_buffer.append"
    assert event["audio"] == "dGVzdA=="


def test_create_response_create_event():
    event = RealtimeSession.create_response_event()
    assert event["type"] == "response.create"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_realtime.py -v`
Expected: FAIL (import error)

**Step 3: Implement Realtime session client**

```python
# backend/app/voice/realtime.py
import base64
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

import websockets

from app.config import settings

logger = logging.getLogger(__name__)

REALTIME_URL = "wss://api.openai.com/v1/realtime"


@dataclass
class SessionConfig:
    instructions: str
    voice: str = "alloy"
    model: str = settings.openai_realtime_model
    input_audio_format: str = "pcm16"
    output_audio_format: str = "pcm16"
    tools: list[dict] = field(default_factory=list)
    turn_detection: dict = field(default_factory=lambda: {"type": "server_vad"})

    def to_session_update_event(self) -> dict:
        return {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": self.voice,
                "input_audio_format": self.input_audio_format,
                "output_audio_format": self.output_audio_format,
                "tools": self.tools,
                "turn_detection": self.turn_detection,
            },
        }


class RealtimeSession:
    def __init__(self, config: SessionConfig, on_tool_call: Callable | None = None):
        self.config = config
        self.on_tool_call = on_tool_call
        self._ws = None
        self._connected = False

    async def connect(self) -> None:
        url = f"{REALTIME_URL}?model={self.config.model}"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
        }
        self._ws = await websockets.connect(url, additional_headers=headers)
        self._connected = True

        # Configure session
        await self._send(self.config.to_session_update_event())
        logger.info("Realtime session connected and configured")

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._connected = False

    async def send_audio(self, audio_b64: str) -> None:
        await self._send(self.create_audio_append_event(audio_b64))

    async def commit_audio(self) -> None:
        await self._send({"type": "input_audio_buffer.commit"})

    async def send_text(self, text: str) -> None:
        """Send a text message (for text-mode testing without audio)."""
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        })
        await self._send(self.create_response_event())

    async def send_tool_result(self, call_id: str, result: str) -> None:
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            },
        })
        await self._send(self.create_response_event())

    async def receive_events(self) -> AsyncIterator[dict]:
        if not self._ws:
            raise RuntimeError("Not connected")
        async for raw in self._ws:
            event = json.loads(raw)
            yield event

    async def _send(self, event: dict) -> None:
        if not self._ws:
            raise RuntimeError("Not connected")
        await self._ws.send(json.dumps(event))

    @staticmethod
    def create_audio_append_event(audio_b64: str) -> dict:
        return {"type": "input_audio_buffer.append", "audio": audio_b64}

    @staticmethod
    def create_response_event() -> dict:
        return {"type": "response.create"}
```

Create empty `backend/app/voice/__init__.py`.

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_realtime.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/voice/ backend/tests/unit/test_realtime.py
git commit -m "feat: add OpenAI Realtime API WebSocket session client"
```

---

### Task 8: Voice Pipeline Orchestrator (Connects All Modules)

**Files:**
- Create: `backend/app/voice/pipeline.py`
- Test: `backend/tests/unit/test_pipeline.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.voice.pipeline import VoicePipeline, CallConfig
from app.agent.state_machine import ConversationStage


def test_call_config_creation():
    config = CallConfig(
        call_id="call-1",
        target_name="Alex Chen",
        target_profile={"name": "Alex Chen", "major": "CS"},
    )
    assert config.call_id == "call-1"
    assert config.mode == "text"  # default


def test_pipeline_initial_state():
    config = CallConfig(call_id="call-1", target_name="Alex", target_profile={"name": "Alex"})
    pipeline = VoicePipeline(config)
    assert pipeline.state_machine.current_stage == ConversationStage.PRE_CALL
    assert pipeline.is_active is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_pipeline.py -v`
Expected: FAIL (import error)

**Step 3: Implement pipeline orchestrator**

```python
# backend/app/voice/pipeline.py
import json
import logging
from dataclasses import dataclass, field

from app.agent.state_machine import ConversationStateMachine, ConversationStage
from app.agent.supervisor import Supervisor
from app.agent.prompts.system import SUPERVISOR_SYSTEM_PROMPT
from app.services.redis_client import RedisService
from app.voice.realtime import RealtimeSession, SessionConfig

logger = logging.getLogger(__name__)


@dataclass
class CallConfig:
    call_id: str
    target_name: str
    target_profile: dict
    mode: str = "text"  # "text", "browser", "twilio"


REALTIME_INSTRUCTIONS_TEMPLATE = """You are a charming, witty person making a casual call to {name}, an MIT student.
You're selling a pen — but make it fun and personalized. You're not a telemarketer, you're a friend-of-a-friend
who happens to have an amazing pen.

Key info about {name}:
{profile_summary}

Current conversation stage: {stage}

Personality: Confident but not pushy. Funny. Relatable. Think Wolf of Wall Street meets your cool friend.

IMPORTANT: Keep responses concise (1-3 sentences). This is a phone call, not an essay.
If you need to make a strategic decision (which pitch to use, how to handle an objection, when to close),
use the delegate_to_supervisor tool and wait for guidance.
"""


class VoicePipeline:
    def __init__(self, config: CallConfig, redis: RedisService | None = None):
        self.config = config
        self.state_machine = ConversationStateMachine()
        self.supervisor = Supervisor(target_profile=config.target_profile, state_machine=self.state_machine)
        self.redis = redis or RedisService()
        self.is_active = False
        self._realtime: RealtimeSession | None = None
        self._transcript: list[dict] = []

    def _build_realtime_instructions(self) -> str:
        profile_summary = "\n".join(f"- {k}: {v}" for k, v in self.config.target_profile.items() if v)
        return REALTIME_INSTRUCTIONS_TEMPLATE.format(
            name=self.config.target_name,
            profile_summary=profile_summary,
            stage=self.state_machine.current_stage.value,
        )

    async def start(self) -> None:
        self.is_active = True
        self.state_machine.transition(ConversationStage.INTRO)

        await self.redis.publish_event("call.started", {
            "call_id": self.config.call_id,
            "target": self.config.target_name,
            "mode": self.config.mode,
        })

        if self.config.mode == "text":
            await self._run_text_mode()
        else:
            await self._run_voice_mode()

    async def _run_text_mode(self) -> None:
        """Run conversation in text mode (for testing / simulation)."""
        # In text mode, we use the supervisor directly without the Realtime API
        logger.info(f"Starting text-mode call to {self.config.target_name}")
        # The actual text conversation loop is driven externally via process_text_input()

    async def process_text_input(self, user_text: str) -> str:
        """Process a text input and return the agent's response. For text mode only."""
        self._transcript.append({"role": "student", "content": user_text})

        response = await self.supervisor.get_response(user_text)

        self._transcript.append({"role": "agent", "content": response})

        await self.redis.publish_event("transcript.update", {
            "call_id": self.config.call_id,
            "stage": self.state_machine.current_stage.value,
            "message": {"role": "agent", "content": response},
        })

        return response

    async def _run_voice_mode(self) -> None:
        """Run conversation with OpenAI Realtime API (browser or Twilio)."""
        session_config = SessionConfig(
            instructions=self._build_realtime_instructions(),
            tools=[
                {
                    "type": "function",
                    "name": "delegate_to_supervisor",
                    "description": "Delegate a strategic decision to the supervisor model for better reasoning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "What you need the supervisor to decide"},
                            "context": {"type": "string", "description": "Relevant conversation context"},
                        },
                        "required": ["question"],
                    },
                },
            ],
        )
        self._realtime = RealtimeSession(config=session_config)
        await self._realtime.connect()

    async def stop(self) -> None:
        self.is_active = False
        if self._realtime:
            await self._realtime.disconnect()

        await self.redis.publish_event("call.ended", {
            "call_id": self.config.call_id,
            "stage": self.state_machine.current_stage.value,
            "transcript_length": len(self._transcript),
        })

    @property
    def transcript(self) -> list[dict]:
        return list(self._transcript)
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_pipeline.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add backend/app/voice/pipeline.py backend/tests/unit/test_pipeline.py
git commit -m "feat: add voice pipeline orchestrator connecting state machine, supervisor, and realtime"
```

---

## Phase 6: FastAPI API Layer

### Task 9: API Routes — Calls & Targets

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/calls.py`
- Create: `backend/app/api/routes/targets.py`
- Create: `backend/app/api/models.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_api_calls.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_api_calls.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_target(client: AsyncClient):
    resp = await client.post("/api/targets", json={
        "name": "Alex Chen",
        "school": "MIT",
        "major": "Computer Science",
        "interests": ["robotics"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alex Chen"
    assert "id" in data


async def test_list_targets(client: AsyncClient):
    await client.post("/api/targets", json={"name": "Alex Chen", "school": "MIT"})
    resp = await client.get("/api/targets")
    assert resp.status_code == 200
    targets = resp.json()
    assert isinstance(targets, list)


async def test_initiate_call(client: AsyncClient):
    # Create target first
    target_resp = await client.post("/api/targets", json={"name": "Alex Chen", "school": "MIT"})
    target_id = target_resp.json()["id"]

    resp = await client.post("/api/calls", json={
        "target_id": target_id,
        "mode": "text",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "call_id" in data
    assert data["status"] == "active"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_api_calls.py -v`
Expected: FAIL (import error)

**Step 3: Create API models**

```python
# backend/app/api/models.py
from pydantic import BaseModel


class TargetCreate(BaseModel):
    name: str
    school: str = ""
    major: str = ""
    year: str = ""
    interests: list[str] = []
    clubs: list[str] = []
    bio: str = ""


class TargetResponse(BaseModel):
    id: str
    name: str
    school: str
    major: str
    year: str
    interests: list[str]
    clubs: list[str]
    bio: str


class CallCreate(BaseModel):
    target_id: str
    mode: str = "text"  # text, browser, twilio


class CallResponse(BaseModel):
    call_id: str
    target_id: str
    target_name: str
    status: str
    mode: str


class TextInput(BaseModel):
    message: str
```

**Step 4: Create targets route**

```python
# backend/app/api/routes/targets.py
import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import TargetCreate, TargetResponse

router = APIRouter(prefix="/api/targets", tags=["targets"])

# In-memory store (swap to Redis/DB later)
_targets: dict[str, dict] = {}


@router.post("", status_code=201, response_model=TargetResponse)
async def create_target(body: TargetCreate):
    target_id = str(uuid.uuid4())[:8]
    target = {"id": target_id, **body.model_dump()}
    _targets[target_id] = target
    return target


@router.get("", response_model=list[TargetResponse])
async def list_targets():
    return list(_targets.values())


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(target_id: str):
    if target_id not in _targets:
        raise HTTPException(status_code=404, detail="Target not found")
    return _targets[target_id]


def get_target_data(target_id: str) -> dict | None:
    return _targets.get(target_id)
```

**Step 5: Create calls route**

```python
# backend/app/api/routes/calls.py
import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import CallCreate, CallResponse, TextInput
from app.api.routes.targets import get_target_data
from app.voice.pipeline import VoicePipeline, CallConfig

router = APIRouter(prefix="/api/calls", tags=["calls"])

# Active pipelines
_pipelines: dict[str, VoicePipeline] = {}


@router.post("", status_code=201, response_model=CallResponse)
async def initiate_call(body: CallCreate):
    target = get_target_data(body.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    call_id = f"call-{uuid.uuid4().hex[:8]}"
    config = CallConfig(
        call_id=call_id,
        target_name=target["name"],
        target_profile=target,
        mode=body.mode,
    )
    pipeline = VoicePipeline(config)
    _pipelines[call_id] = pipeline

    await pipeline.start()

    return CallResponse(
        call_id=call_id,
        target_id=body.target_id,
        target_name=target["name"],
        status="active",
        mode=body.mode,
    )


@router.post("/{call_id}/text", response_model=dict)
async def send_text_message(call_id: str, body: TextInput):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    if not pipeline.is_active:
        raise HTTPException(status_code=400, detail="Call is not active")

    response = await pipeline.process_text_input(body.message)
    return {
        "response": response,
        "stage": pipeline.state_machine.current_stage.value,
    }


@router.post("/{call_id}/end")
async def end_call(call_id: str):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    await pipeline.stop()
    return {"status": "ended", "transcript": pipeline.transcript}


@router.get("/{call_id}")
async def get_call(call_id: str):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        "call_id": call_id,
        "is_active": pipeline.is_active,
        "stage": pipeline.state_machine.current_stage.value,
        "transcript": pipeline.transcript,
    }
```

**Step 6: Update main.py to include routers**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import calls, targets
from app.config import settings

app = FastAPI(title="CORD Voice Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(targets.router)
app.include_router(calls.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

Create empty `backend/app/api/__init__.py` and `backend/app/api/routes/__init__.py`.

**Step 7: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_api_calls.py -v`
Expected: All 4 tests PASS

**Step 8: Commit**

```bash
git add backend/app/api/ backend/app/main.py backend/tests/unit/test_api_calls.py
git commit -m "feat: add REST API routes for targets and calls with text-mode conversation"
```

---

### Task 10: WebSocket Endpoint for Frontend Dashboard

**Files:**
- Create: `backend/app/api/routes/ws.py`
- Modify: `backend/app/main.py` (add WS router)

**Step 1: Implement WebSocket endpoint**

```python
# backend/app/api/routes/ws.py
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.redis_client import RedisService, EVENT_CHANNEL

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)

    async def broadcast(self, message: str) -> None:
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self._connections.remove(ws)


manager = ConnectionManager()


@router.websocket("/ws/events")
async def events_websocket(ws: WebSocket):
    await manager.connect(ws)
    redis = RedisService()
    pubsub = redis.client.pubsub()
    await pubsub.subscribe(EVENT_CHANNEL)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(EVENT_CHANNEL)
        manager.disconnect(ws)
```

**Step 2: Add WS router to main.py**

Add `from app.api.routes import ws` to imports and `app.include_router(ws.router)` in main.py.

**Step 3: Commit**

```bash
git add backend/app/api/routes/ws.py backend/app/main.py
git commit -m "feat: add WebSocket endpoint for real-time dashboard events via Redis pub/sub"
```

---

## Phase 7: Analytics (Deepgram + Post-Call Analysis)

### Task 11: Deepgram Transcription & AI Analysis

**Files:**
- Create: `backend/app/analytics/__init__.py`
- Create: `backend/app/analytics/transcription.py`
- Create: `backend/app/analytics/analyzer.py`
- Test: `backend/tests/unit/test_analyzer.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_analyzer.py
import pytest
from unittest.mock import AsyncMock, patch

from app.analytics.analyzer import CallAnalyzer


def test_analyzer_formats_transcript():
    analyzer = CallAnalyzer()
    transcript = [
        {"role": "agent", "content": "Hey Alex! Got a minute?"},
        {"role": "student", "content": "Uh, sure, who is this?"},
        {"role": "agent", "content": "I'm selling the best pen you'll ever own."},
    ]
    formatted = analyzer._format_transcript(transcript)
    assert "Agent:" in formatted
    assert "Student:" in formatted
    assert "best pen" in formatted
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_analyzer.py -v`
Expected: FAIL

**Step 3: Implement transcription module**

```python
# backend/app/analytics/transcription.py
import logging

from deepgram import DeepgramClient, PrerecordedOptions

from app.config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/wav") -> dict:
    """Transcribe audio using Deepgram. Returns transcript with speaker diarization."""
    if not settings.deepgram_api_key:
        logger.warning("Deepgram API key not set, skipping transcription")
        return {"transcript": "", "words": []}

    client = DeepgramClient(settings.deepgram_api_key)
    options = PrerecordedOptions(
        model="nova-2",
        smart_format=True,
        diarize=True,
    )
    source = {"buffer": audio_bytes, "mimetype": mimetype}
    response = await client.listen.asyncrest.v("1").transcribe_file(source, options)
    result = response.to_dict()

    return {
        "transcript": result.get("results", {}).get("channels", [{}])[0]
            .get("alternatives", [{}])[0].get("transcript", ""),
        "words": result.get("results", {}).get("channels", [{}])[0]
            .get("alternatives", [{}])[0].get("words", []),
    }
```

**Step 4: Implement analyzer**

```python
# backend/app/analytics/analyzer.py
import json

from openai import AsyncOpenAI

from app.config import settings

ANALYSIS_PROMPT = """Analyze this sales call transcript where an agent tried to sell a pen to an MIT student.

Transcript:
{transcript}

Provide your analysis as JSON with these fields:
- effectiveness_score: 1-10 rating of overall persuasion effectiveness
- tactics_used: list of persuasion tactics identified (e.g., "rapport building", "social proof", "scarcity")
- tactics_that_worked: which tactics seemed to land well
- tactics_that_failed: which tactics fell flat or backfired
- objections_encountered: list of objections the student raised
- objection_handling_quality: 1-10 rating
- key_moments: list of {{timestamp_approx, description, impact}} for pivotal moments
- sentiment_arc: brief description of how the student's receptiveness changed over time
- improvement_suggestions: 3-5 specific, actionable suggestions for next time
- outcome: "sold", "rejected", "undecided"

Return ONLY valid JSON, no markdown formatting.
"""


class CallAnalyzer:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    def _format_transcript(self, transcript: list[dict]) -> str:
        lines = []
        for entry in transcript:
            role = entry["role"].capitalize()
            if role == "Agent":
                lines.append(f"Agent: {entry['content']}")
            else:
                lines.append(f"Student: {entry['content']}")
        return "\n".join(lines)

    async def analyze(self, transcript: list[dict]) -> dict:
        formatted = self._format_transcript(transcript)
        response = await self._client.chat.completions.create(
            model=settings.openai_supervisor_model,
            messages=[
                {"role": "user", "content": ANALYSIS_PROMPT.format(transcript=formatted)},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
```

Create empty `backend/app/analytics/__init__.py`.

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_analyzer.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/analytics/ backend/tests/unit/test_analyzer.py
git commit -m "feat: add Deepgram transcription and GPT-5.2 post-call analysis"
```

---

## Phase 8: Next.js Frontend Dashboard

### Task 12: Next.js Project Setup

**Step 1: Scaffold Next.js 15 project**

Run:
```bash
cd /Users/datct/CSProjects/PersonalProjects/cord && npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
```

**Step 2: Install additional dependencies**

Run:
```bash
cd frontend && npm install recharts
```

**Step 3: Create API client**

```typescript
// frontend/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface Target {
  id: string;
  name: string;
  school: string;
  major: string;
  year: string;
  interests: string[];
  clubs: string[];
  bio: string;
}

export interface Call {
  call_id: string;
  target_id: string;
  target_name: string;
  status: string;
  mode: string;
}

export interface CallDetail {
  call_id: string;
  is_active: boolean;
  stage: string;
  transcript: { role: string; content: string }[];
}

export const api = {
  targets: {
    list: () => fetchApi<Target[]>("/api/targets"),
    create: (data: Omit<Target, "id">) =>
      fetchApi<Target>("/api/targets", { method: "POST", body: JSON.stringify(data) }),
  },
  calls: {
    create: (data: { target_id: string; mode: string }) =>
      fetchApi<Call>("/api/calls", { method: "POST", body: JSON.stringify(data) }),
    get: (callId: string) => fetchApi<CallDetail>(`/api/calls/${callId}`),
    sendText: (callId: string, message: string) =>
      fetchApi<{ response: string; stage: string }>(`/api/calls/${callId}/text`, {
        method: "POST",
        body: JSON.stringify({ message }),
      }),
    end: (callId: string) =>
      fetchApi<{ status: string; transcript: any[] }>(`/api/calls/${callId}/end`, { method: "POST" }),
  },
};
```

**Step 4: Create WebSocket hook**

```typescript
// frontend/src/hooks/useWebSocket.ts
"use client";
import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/events";

interface WSEvent {
  event: string;
  [key: string]: any;
}

export function useWebSocket() {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data) as WSEvent;
      setEvents((prev) => [...prev.slice(-100), data]); // Keep last 100
    };

    return () => ws.close();
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, clearEvents };
}
```

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Next.js 15 frontend with API client and WebSocket hook"
```

---

### Task 13: Dashboard Home Page

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/layout.tsx` (update)
- Create: `frontend/src/components/CallCard.tsx`
- Create: `frontend/src/components/NewCallDialog.tsx`

**Step 1: Build the dashboard home page**

```tsx
// frontend/src/app/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api, type Call, type Target } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { CallCard } from "@/components/CallCard";
import { NewCallDialog } from "@/components/NewCallDialog";

export default function Dashboard() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [activeCalls, setActiveCalls] = useState<Call[]>([]);
  const [showNewCall, setShowNewCall] = useState(false);
  const { events, connected } = useWebSocket();

  useEffect(() => {
    api.targets.list().then(setTargets).catch(() => {});
  }, []);

  const handleNewCall = async (targetId: string) => {
    const call = await api.calls.create({ target_id: targetId, mode: "text" });
    setActiveCalls((prev) => [...prev, call]);
    setShowNewCall(false);
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-6xl mx-auto">
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">CORD</h1>
            <p className="text-zinc-400 text-sm">Voice Persuasion Agent</p>
          </div>
          <div className="flex items-center gap-4">
            <span className={`text-xs px-2 py-1 rounded ${connected ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
              {connected ? "Connected" : "Disconnected"}
            </span>
            <button
              onClick={() => setShowNewCall(true)}
              className="bg-zinc-100 text-zinc-900 px-4 py-2 rounded-lg text-sm font-medium hover:bg-zinc-200 transition"
            >
              + New Call
            </button>
          </div>
        </header>

        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-4">Active Calls</h2>
          {activeCalls.length === 0 ? (
            <p className="text-zinc-500 text-sm">No active calls. Start one above.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {activeCalls.map((call) => (
                <CallCard key={call.call_id} call={call} />
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-4">Recent Events</h2>
          <div className="bg-zinc-900 rounded-lg p-4 max-h-64 overflow-y-auto font-mono text-xs">
            {events.length === 0 ? (
              <p className="text-zinc-500">Waiting for events...</p>
            ) : (
              events.map((e, i) => (
                <div key={i} className="py-1 border-b border-zinc-800">
                  <span className="text-zinc-500">{e.event}</span>{" "}
                  <span className="text-zinc-300">{JSON.stringify(e, null, 0)}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {showNewCall && (
        <NewCallDialog
          targets={targets}
          onStart={handleNewCall}
          onClose={() => setShowNewCall(false)}
        />
      )}
    </main>
  );
}
```

**Step 2: Create CallCard component**

```tsx
// frontend/src/components/CallCard.tsx
"use client";
import Link from "next/link";
import type { Call } from "@/lib/api";

export function CallCard({ call }: { call: Call }) {
  return (
    <Link href={`/calls/${call.call_id}`}>
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-600 transition cursor-pointer">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-medium">{call.target_name}</h3>
          <span className="text-xs px-2 py-0.5 rounded bg-green-900 text-green-300">
            {call.status}
          </span>
        </div>
        <p className="text-zinc-400 text-sm">Mode: {call.mode}</p>
        <p className="text-zinc-500 text-xs font-mono">{call.call_id}</p>
      </div>
    </Link>
  );
}
```

**Step 3: Create NewCallDialog component**

```tsx
// frontend/src/components/NewCallDialog.tsx
"use client";
import { useState } from "react";
import type { Target } from "@/lib/api";

interface Props {
  targets: Target[];
  onStart: (targetId: string) => void;
  onClose: () => void;
}

export function NewCallDialog({ targets, onStart, onClose }: Props) {
  const [selectedId, setSelectedId] = useState("");

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">Start New Call</h2>
        {targets.length === 0 ? (
          <p className="text-zinc-400 text-sm mb-4">No targets yet. Add one on the Targets page first.</p>
        ) : (
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-2 text-sm mb-4"
          >
            <option value="">Select a target...</option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} — {t.school} {t.major}
              </option>
            ))}
          </select>
        )}
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200">
            Cancel
          </button>
          <button
            onClick={() => selectedId && onStart(selectedId)}
            disabled={!selectedId}
            className="bg-zinc-100 text-zinc-900 px-4 py-2 rounded-lg text-sm font-medium hover:bg-zinc-200 transition disabled:opacity-40"
          >
            Start Call
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: add dashboard home page with active calls, events feed, and new call dialog"
```

---

### Task 14: Call Detail Page (Live Conversation)

**Files:**
- Create: `frontend/src/app/calls/[id]/page.tsx`

**Step 1: Build the call detail page with live text chat**

```tsx
// frontend/src/app/calls/[id]/page.tsx
"use client";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { api, type CallDetail } from "@/lib/api";

const STAGE_COLORS: Record<string, string> = {
  pre_call: "bg-zinc-700",
  intro: "bg-blue-900 text-blue-300",
  pitch: "bg-purple-900 text-purple-300",
  objection: "bg-orange-900 text-orange-300",
  close: "bg-green-900 text-green-300",
  logistics: "bg-cyan-900 text-cyan-300",
  wrap_up: "bg-zinc-600",
};

export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (id) api.calls.get(id).then(setCall).catch(() => {});
  }, [id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [call?.transcript]);

  const sendMessage = async () => {
    if (!input.trim() || !id || sending) return;
    setSending(true);
    const message = input;
    setInput("");

    // Optimistic update
    setCall((prev) =>
      prev ? { ...prev, transcript: [...prev.transcript, { role: "student", content: message }] } : prev
    );

    const result = await api.calls.sendText(id, message);

    setCall((prev) =>
      prev
        ? {
            ...prev,
            stage: result.stage,
            transcript: [...prev.transcript, { role: "agent", content: result.response }],
          }
        : prev
    );
    setSending(false);
  };

  const endCall = async () => {
    if (!id) return;
    await api.calls.end(id);
    setCall((prev) => (prev ? { ...prev, is_active: false } : prev));
  };

  if (!call) return <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">Loading...</div>;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="/" className="text-zinc-400 hover:text-zinc-200 text-sm">&larr; Back</a>
          <h1 className="font-semibold">Call {call.call_id}</h1>
          <span className={`text-xs px-2 py-0.5 rounded ${STAGE_COLORS[call.stage] || "bg-zinc-700"}`}>
            {call.stage}
          </span>
        </div>
        {call.is_active && (
          <button onClick={endCall} className="text-red-400 hover:text-red-300 text-sm">
            End Call
          </button>
        )}
      </header>

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {call.transcript.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "agent" ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-md px-4 py-2 rounded-2xl text-sm ${
                msg.role === "agent"
                  ? "bg-zinc-800 text-zinc-100"
                  : "bg-blue-600 text-white"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      {call.is_active && (
        <div className="border-t border-zinc-800 p-4">
          <div className="flex gap-2 max-w-4xl mx-auto">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Type as the student..."
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-zinc-500"
            />
            <button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
              className="bg-zinc-100 text-zinc-900 px-4 py-2 rounded-xl text-sm font-medium hover:bg-zinc-200 transition disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/calls/
git commit -m "feat: add call detail page with live text conversation and stage indicator"
```

---

### Task 15: Targets Management Page

**Files:**
- Create: `frontend/src/app/targets/page.tsx`

**Step 1: Build targets page**

```tsx
// frontend/src/app/targets/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api, type Target } from "@/lib/api";

export default function TargetsPage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [form, setForm] = useState({ name: "", school: "MIT", major: "", interests: "" });

  useEffect(() => {
    api.targets.list().then(setTargets).catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!form.name) return;
    const target = await api.targets.create({
      name: form.name,
      school: form.school,
      major: form.major,
      year: "",
      interests: form.interests.split(",").map((s) => s.trim()).filter(Boolean),
      clubs: [],
      bio: "",
    });
    setTargets((prev) => [...prev, target]);
    setForm({ name: "", school: "MIT", major: "", interests: "" });
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <a href="/" className="text-zinc-400 hover:text-zinc-200 text-sm">&larr; Back</a>
          <h1 className="text-2xl font-bold">Targets</h1>
        </div>

        {/* Add target form */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 mb-8">
          <h2 className="font-medium mb-3">Add Target</h2>
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="School" value={form.school} onChange={(e) => setForm({ ...form, school: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="Major" value={form.major} onChange={(e) => setForm({ ...form, major: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="Interests (comma-separated)" value={form.interests} onChange={(e) => setForm({ ...form, interests: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
          </div>
          <button onClick={handleCreate} className="mt-3 bg-zinc-100 text-zinc-900 px-4 py-2 rounded-lg text-sm font-medium hover:bg-zinc-200 transition">Add Target</button>
        </div>

        {/* Target list */}
        <div className="space-y-3">
          {targets.map((t) => (
            <div key={t.id} className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{t.name}</h3>
                <span className="text-xs text-zinc-500 font-mono">{t.id}</span>
              </div>
              <p className="text-sm text-zinc-400">{t.school} — {t.major}</p>
              {t.interests.length > 0 && (
                <div className="flex gap-1 mt-2">
                  {t.interests.map((i) => (
                    <span key={i} className="text-xs bg-zinc-800 px-2 py-0.5 rounded">{i}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/targets/
git commit -m "feat: add targets management page with create form and listing"
```

---

## Phase 9: Twilio Phone Call Integration

### Task 16: Twilio Media Streams + Audio Bridging

**Files:**
- Create: `backend/app/voice/twilio_stream.py`
- Create: `backend/app/voice/audio.py`
- Create: `backend/app/api/routes/twilio_webhook.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_audio.py`

**Step 1: Write failing test for audio conversion**

```python
# backend/tests/unit/test_audio.py
import base64

from app.voice.audio import mulaw_to_pcm16, pcm16_to_mulaw


def test_mulaw_to_pcm16_and_back():
    # Create some mulaw bytes (silence = 0xFF in mulaw)
    mulaw_data = bytes([0xFF] * 160)  # 20ms of silence at 8kHz
    pcm_data = mulaw_to_pcm16(mulaw_data)
    assert len(pcm_data) > 0
    # PCM16 at 24kHz for 20ms = 960 samples * 2 bytes = 1920 bytes
    # (8kHz -> 24kHz = 3x upsampling, 160 samples -> 480 samples * 2 bytes)


def test_pcm16_to_mulaw():
    # Create PCM16 silence
    pcm_data = bytes([0x00] * 960)  # 480 samples of silence
    mulaw_data = pcm16_to_mulaw(pcm_data)
    assert len(mulaw_data) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_audio.py -v`
Expected: FAIL

**Step 3: Implement audio conversion**

```python
# backend/app/voice/audio.py
import audioop
import struct


def mulaw_to_pcm16(mulaw_bytes: bytes, from_rate: int = 8000, to_rate: int = 24000) -> bytes:
    """Convert mulaw 8kHz (Twilio) to PCM16 24kHz (OpenAI Realtime)."""
    # Decode mulaw to linear PCM16
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    # Resample from 8kHz to 24kHz
    pcm_24k, _ = audioop.ratecv(pcm_8k, 2, 1, from_rate, to_rate, None)
    return pcm_24k


def pcm16_to_mulaw(pcm_bytes: bytes, from_rate: int = 24000, to_rate: int = 8000) -> bytes:
    """Convert PCM16 24kHz (OpenAI Realtime) to mulaw 8kHz (Twilio)."""
    # Resample from 24kHz to 8kHz
    pcm_8k, _ = audioop.ratecv(pcm_bytes, 2, 1, from_rate, to_rate, None)
    # Encode to mulaw
    mulaw = audioop.lin2ulaw(pcm_8k, 2)
    return mulaw
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_audio.py -v`
Expected: PASS

**Step 5: Implement Twilio Media Stream handler**

```python
# backend/app/voice/twilio_stream.py
import base64
import json
import logging

from fastapi import WebSocket

from app.voice.audio import mulaw_to_pcm16, pcm16_to_mulaw
from app.voice.realtime import RealtimeSession

logger = logging.getLogger(__name__)


class TwilioMediaStreamHandler:
    """Bridges Twilio Media Streams <-> OpenAI Realtime API."""

    def __init__(self, twilio_ws: WebSocket, realtime: RealtimeSession):
        self.twilio_ws = twilio_ws
        self.realtime = realtime
        self.stream_sid: str = ""

    async def handle_twilio_message(self, data: dict) -> None:
        event = data.get("event")

        if event == "start":
            self.stream_sid = data["start"]["streamSid"]
            logger.info(f"Twilio stream started: {self.stream_sid}")

        elif event == "media":
            # Convert Twilio mulaw to PCM16 and forward to OpenAI
            mulaw_b64 = data["media"]["payload"]
            mulaw_bytes = base64.b64decode(mulaw_b64)
            pcm_bytes = mulaw_to_pcm16(mulaw_bytes)
            pcm_b64 = base64.b64encode(pcm_bytes).decode()
            await self.realtime.send_audio(pcm_b64)

        elif event == "stop":
            logger.info("Twilio stream stopped")

    async def send_audio_to_twilio(self, pcm_b64: str) -> None:
        """Convert PCM16 from OpenAI to mulaw and send to Twilio."""
        pcm_bytes = base64.b64decode(pcm_b64)
        mulaw_bytes = pcm16_to_mulaw(pcm_bytes)
        mulaw_b64 = base64.b64encode(mulaw_bytes).decode()

        await self.twilio_ws.send_json({
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": mulaw_b64},
        })
```

**Step 6: Create Twilio webhook route**

```python
# backend/app/api/routes/twilio_webhook.py
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.config import settings

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


@router.post("/voice")
async def voice_webhook(request: Request):
    """Twilio hits this when a call connects. Returns TwiML to start a Media Stream."""
    host = request.headers.get("host", "localhost:8000")
    ws_url = f"wss://{host}/ws/twilio-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")
```

**Step 7: Add Twilio webhook router to main.py**

Add `from app.api.routes import twilio_webhook` and `app.include_router(twilio_webhook.router)`.

**Step 8: Commit**

```bash
git add backend/app/voice/audio.py backend/app/voice/twilio_stream.py backend/app/api/routes/twilio_webhook.py backend/tests/unit/test_audio.py backend/app/main.py
git commit -m "feat: add Twilio Media Stream handler with mulaw<->PCM16 audio bridging"
```

---

## Phase 10: Simulated Caller Testing

### Task 17: Student Simulator for Automated Testing

**Files:**
- Create: `backend/tests/simulation/__init__.py`
- Create: `backend/tests/simulation/student_simulator.py`
- Create: `backend/tests/simulation/test_simulated_call.py`

**Step 1: Create student simulator**

```python
# backend/tests/simulation/student_simulator.py
from openai import AsyncOpenAI

from app.config import settings

PERSONALITY_PROMPTS = {
    "easy_sell": (
        "You are a friendly MIT sophomore who is curious about new things. "
        "You're open to buying a pen if the pitch is decent. You ask a few questions "
        "but are generally positive. Budget isn't a concern."
    ),
    "hard_sell": (
        "You are a skeptical MIT senior who hates being sold to. "
        "You challenge every claim, ask for proof, and are very resistant. "
        "You might buy if genuinely convinced but it takes a lot."
    ),
    "busy_no_time": (
        "You are a stressed MIT junior rushing to a problem set deadline. "
        "You have literally 30 seconds. Be polite but firm that you need to go. "
        "If they can hook you in one sentence, maybe you'll stay."
    ),
    "curious_but_broke": (
        "You are an MIT freshman who finds the whole thing amusing. "
        "You're interested and engaged but keep bringing up that you're broke. "
        "You might buy if the price is very low or there's a creative deal."
    ),
}


class StudentSimulator:
    def __init__(self, personality: str = "easy_sell"):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._personality = personality
        self._messages: list[dict] = []
        self._system = (
            f"You are an MIT student receiving a phone call from someone trying to sell you a pen. "
            f"Stay in character. Respond naturally as a real person would — short, conversational.\n\n"
            f"Your personality: {PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS['easy_sell'])}\n\n"
            f"IMPORTANT: Keep responses to 1-2 sentences. This is a phone call."
        )

    async def respond(self, agent_message: str) -> str:
        self._messages.append({"role": "user", "content": agent_message})
        response = await self._client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {"role": "system", "content": self._system},
                *self._messages,
            ],
            max_tokens=100,
        )
        text = response.choices[0].message.content or ""
        self._messages.append({"role": "assistant", "content": text})
        return text
```

**Step 2: Create simulated call test**

```python
# backend/tests/simulation/test_simulated_call.py
import pytest

from tests.simulation.student_simulator import StudentSimulator
from app.voice.pipeline import VoicePipeline, CallConfig


MAX_TURNS = 15  # Safety limit to prevent infinite loops


@pytest.mark.skipif(
    not __import__("os").getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY for live simulation",
)
class TestSimulatedCall:
    async def test_easy_sell_completes(self):
        """Run a full text-mode conversation with an easy-sell student."""
        simulator = StudentSimulator(personality="easy_sell")
        config = CallConfig(
            call_id="sim-easy-1",
            target_name="Alex Chen",
            target_profile={
                "name": "Alex Chen",
                "school": "MIT",
                "major": "Computer Science",
                "interests": ["robotics", "coffee"],
            },
        )
        pipeline = VoicePipeline(config)
        await pipeline.start()

        # Agent goes first
        agent_msg = await pipeline.process_text_input("Hello?")
        turns = 0

        while pipeline.is_active and turns < MAX_TURNS:
            student_msg = await simulator.respond(agent_msg)
            agent_msg = await pipeline.process_text_input(student_msg)
            turns += 1

        transcript = pipeline.transcript
        assert len(transcript) > 2, "Conversation should have multiple exchanges"
        assert turns < MAX_TURNS, "Conversation should not hit safety limit"

    async def test_hard_sell_handles_objections(self):
        """Run a conversation with a hard-sell student — verify agent handles objections."""
        simulator = StudentSimulator(personality="hard_sell")
        config = CallConfig(
            call_id="sim-hard-1",
            target_name="Jordan Lee",
            target_profile={
                "name": "Jordan Lee",
                "school": "MIT",
                "major": "Physics",
                "interests": ["quantum computing"],
            },
        )
        pipeline = VoicePipeline(config)
        await pipeline.start()

        agent_msg = await pipeline.process_text_input("Hello?")
        turns = 0

        while pipeline.is_active and turns < MAX_TURNS:
            student_msg = await simulator.respond(agent_msg)
            agent_msg = await pipeline.process_text_input(student_msg)
            turns += 1

        transcript = pipeline.transcript
        assert len(transcript) > 2
```

Create empty `backend/tests/simulation/__init__.py`.

**Step 3: Run simulation test (requires API key)**

Run: `cd backend && python -m pytest tests/simulation/ -v -s --timeout=120`
Expected: Tests run live conversations, PASS if within turn limits.

**Step 4: Commit**

```bash
git add backend/tests/simulation/
git commit -m "feat: add student simulator and automated conversation tests"
```

---

## Phase 11: Docker & Distributed Infrastructure

### Task 18: Dockerfiles & Docker Compose

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `docker-compose.test.yml`

**Step 1: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
```

**Step 3: Create docker-compose.yml for dev**

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - ./backend/app:/app/app  # Hot reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/events
    depends_on:
      - backend
```

**Step 4: Create docker-compose.test.yml for load testing**

```yaml
# docker-compose.test.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  gateway:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  worker-1:
    build: ./backend
    env_file: .env
    environment:
      - REDIS_URL=redis://redis:6379/0
      - WORKER_ID=1
      - WORKER_MODE=true
    depends_on:
      - redis

  worker-2:
    build: ./backend
    env_file: .env
    environment:
      - REDIS_ID=2
      - REDIS_URL=redis://redis:6379/0
      - WORKER_MODE=true
    depends_on:
      - redis

  worker-3:
    build: ./backend
    env_file: .env
    environment:
      - WORKER_ID=3
      - REDIS_URL=redis://redis:6379/0
      - WORKER_MODE=true
    depends_on:
      - redis
```

**Step 5: Verify docker compose builds**

Run: `docker compose build`
Expected: Both images build successfully

**Step 6: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile docker-compose.yml docker-compose.test.yml
git commit -m "feat: add Dockerfiles and Docker Compose for dev and load testing"
```

---

## Phase 12: Post-Call Analysis Page

### Task 19: Analysis Page in Frontend

**Files:**
- Create: `frontend/src/app/calls/[id]/analysis/page.tsx`

**Step 1: Build analysis page**

```tsx
// frontend/src/app/calls/[id]/analysis/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

interface Analysis {
  effectiveness_score: number;
  tactics_used: string[];
  tactics_that_worked: string[];
  tactics_that_failed: string[];
  objections_encountered: string[];
  objection_handling_quality: number;
  key_moments: { timestamp_approx: string; description: string; impact: string }[];
  sentiment_arc: string;
  improvement_suggestions: string[];
  outcome: string;
}

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      // TODO: wire up to backend analysis endpoint
      // For now, show placeholder
      setLoading(false);
    }
  }, [id]);

  if (loading) return <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">Analyzing...</div>;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <a href={`/calls/${id}`} className="text-zinc-400 hover:text-zinc-200 text-sm">&larr; Back to call</a>
          <h1 className="text-2xl font-bold">Call Analysis</h1>
        </div>

        {analysis ? (
          <div className="space-y-6">
            {/* Score */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-center">
                <p className="text-zinc-400 text-sm">Effectiveness</p>
                <p className="text-4xl font-bold">{analysis.effectiveness_score}/10</p>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-center">
                <p className="text-zinc-400 text-sm">Objection Handling</p>
                <p className="text-4xl font-bold">{analysis.objection_handling_quality}/10</p>
              </div>
            </div>

            {/* Outcome */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h2 className="font-medium mb-2">Outcome</h2>
              <span className={`px-3 py-1 rounded text-sm ${analysis.outcome === "sold" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
                {analysis.outcome}
              </span>
            </div>

            {/* Sentiment Arc */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h2 className="font-medium mb-2">Sentiment Arc</h2>
              <p className="text-zinc-400 text-sm">{analysis.sentiment_arc}</p>
            </div>

            {/* Tactics */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <h2 className="font-medium mb-2 text-green-400">Worked</h2>
                <ul className="text-sm text-zinc-300 space-y-1">
                  {analysis.tactics_that_worked.map((t, i) => <li key={i}>+ {t}</li>)}
                </ul>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <h2 className="font-medium mb-2 text-red-400">Didn't Work</h2>
                <ul className="text-sm text-zinc-300 space-y-1">
                  {analysis.tactics_that_failed.map((t, i) => <li key={i}>- {t}</li>)}
                </ul>
              </div>
            </div>

            {/* Suggestions */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h2 className="font-medium mb-2">Improvement Suggestions</h2>
              <ul className="text-sm text-zinc-300 space-y-2">
                {analysis.improvement_suggestions.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-zinc-500">{i + 1}.</span> {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 text-center">
            <p className="text-zinc-400">Analysis not yet available. End the call first, then request analysis.</p>
          </div>
        )}
      </div>
    </main>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/calls/
git commit -m "feat: add post-call analysis page with effectiveness scores, tactics, and suggestions"
```

---

## Summary: Build Order

| Phase | Tasks | What It Delivers |
|-------|-------|-----------------|
| 1 | 1-2 | Working FastAPI app with Redis |
| 2 | 3 | Conversation state machine |
| 3 | 4-5 | GPT-5.2 supervisor with tool calling |
| 4 | 6 | Pre-call research/enrichment |
| 5 | 7-8 | OpenAI Realtime API client + voice pipeline |
| 6 | 9-10 | REST API + WebSocket for dashboard |
| 7 | 11 | Deepgram transcription + AI analysis |
| 8 | 12-15 | Full Next.js dashboard (home, call detail, targets) |
| 9 | 16 | Twilio phone calls with audio bridging |
| 10 | 17 | Simulated caller tests |
| 11 | 18 | Docker + Docker Compose (dev + load test) |
| 12 | 19 | Analysis page in frontend |

**After Phase 6 you have a working text-mode demo.** After Phase 8 you have the full dashboard. Phases 9-12 add phone calls, testing, and distributed infra.
