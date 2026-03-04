from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import settings
from app.voice.prompt import build_realtime_prompt
from tests.simulation.personas import StudentPersona
from tests.simulation.simulator import StudentSimulator

_SALE_PATTERNS = [
    r"\b(sure|okay|fine|alright|deal|yes|let'?s do it|i'?ll take it|i'?m in|you win|sold)\b",
    r"where (do|should|can) (we|i) meet",
    r"when (do|should|can) (we|i) (meet|pick it up|get it)",
]
_REFUSE_PATTERNS = [
    r"(please )?(stop|leave me alone|don'?t call|hanging up|not interested|go away)",
    r"i('?m| am) (hanging up|done|leaving)",
    r"(bye|goodbye)\s*$",
]
_WRAP_UP_PATTERNS = [
    r"(no worries|no problem|alright then|okay then|fair enough|take care)",
    r"(change your mind|know who to call|hit me up|catch you later)",
]


def detect_outcome(text: str) -> str | None:
    text_lower = text.lower().strip()
    for pattern in _SALE_PATTERNS:
        if re.search(pattern, text_lower):
            return "sold"
    for pattern in _REFUSE_PATTERNS:
        if re.search(pattern, text_lower):
            return "refused"
    for pattern in _WRAP_UP_PATTERNS:
        if re.search(pattern, text_lower):
            return "wrapped_up"
    return None


@dataclass
class SimulationResult:
    transcript: list[dict] = field(default_factory=list)
    turns: int = 0
    outcome: str = "max_turns"
    duration_seconds: float = 0.0
    persona_name: str = ""
    max_turns_hit: bool = False


class CallRunner:
    def __init__(self, client: AsyncOpenAI | None = None, model: str | None = None):
        self._client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.openai_supervisor_model

    async def run(
        self,
        target_profile: dict,
        persona: StudentPersona,
        max_turns: int = 30,
    ) -> SimulationResult:
        start = time.monotonic()
        agent_system = build_realtime_prompt(target_profile["name"], target_profile)
        simulator = StudentSimulator(persona, client=self._client, model=self._model)
        transcript: list[dict] = []
        result = SimulationResult(persona_name=persona.name)

        for turn in range(max_turns):
            # Agent turn
            agent_response = await self._agent_turn(agent_system, transcript)
            transcript.append({"role": "agent", "content": agent_response})

            agent_outcome = detect_outcome(agent_response)
            if agent_outcome == "wrapped_up":
                result.outcome = "wrapped_up"
                break

            # Student turn
            student_response = await simulator.respond(transcript)
            transcript.append({"role": "user", "content": student_response})

            student_outcome = detect_outcome(student_response)
            if student_outcome == "sold":
                result.outcome = "sold"
                break
            if student_outcome == "refused":
                result.outcome = "refused"
                break
        else:
            result.max_turns_hit = True
            result.outcome = "max_turns"

        result.transcript = transcript
        result.turns = len(transcript)
        result.duration_seconds = round(time.monotonic() - start, 2)
        return result

    async def _agent_turn(self, system_prompt: str, transcript: list[dict]) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        for entry in transcript:
            role = "assistant" if entry["role"] == "agent" else "user"
            messages.append({"role": role, "content": entry["content"]})
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_completion_tokens=200,
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()
