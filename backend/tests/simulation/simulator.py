from __future__ import annotations

from openai import AsyncOpenAI

from app.config import settings
from tests.simulation.personas import StudentPersona

_OBJECTION_STYLE_DESC = {
    "polite_decline": "politely say no and give a reason. You're not rude, just firm.",
    "aggressive": "push back hard. You're annoyed and don't sugarcoat it.",
    "passive": "dodge and deflect. You say 'maybe' and 'I'll think about it' without committing.",
    "curious_but_broke": "ask questions and seem interested, but keep bringing up that you can't afford it.",
}

_TIME_PRESSURE_DESC = {
    "none": "You have time to chat. No rush.",
    "late_for_class": "You're literally about to walk into class. Every second counts.",
    "walking_with_friends": "You're with friends and can't have a long private conversation.",
}

_HIDDEN_GOAL_INSTRUCTIONS = {
    "buy": (
        "You're open to buying. You'll resist a little (nobody says yes immediately), "
        "but if the pitch is decent and they address your concerns, you'll agree."
    ),
    "refuse": (
        "You are NOT buying this pen, period. Be consistent in your refusal. "
        "You can engage with their arguments, but ultimately you're not interested. "
        "After 3-4 attempts, make it clear you want to end the conversation."
    ),
    "stall": (
        "You're not saying yes or no. You keep the conversation going but never commit. "
        "Use phrases like 'I'll think about it', 'maybe later', 'send me a link'. "
        "You're not hostile, just non-committal."
    ),
    "agree_then_back_out": (
        "Play along and seem increasingly interested. Around the 4th-5th exchange, "
        "agree to buy. Then 1-2 turns later, say something like 'actually wait, "
        "I changed my mind' or 'hmm, actually I don't think I need it.' "
        "This tests whether the agent can recover from a reversal."
    ),
}


def build_student_prompt(persona: StudentPersona) -> str:
    traits_str = ", ".join(persona.personality_traits) if persona.personality_traits else "normal"
    skepticism_label = (
        "very low"
        if persona.skepticism < 0.3
        else "low"
        if persona.skepticism < 0.5
        else "moderate"
        if persona.skepticism < 0.7
        else "high"
        if persona.skepticism < 0.9
        else "very high"
    )
    budget_label = (
        "money is not a concern"
        if persona.budget_sensitivity < 0.3
        else "you're a bit careful with money"
        if persona.budget_sensitivity < 0.6
        else "you're on a tight budget"
        if persona.budget_sensitivity < 0.8
        else "you are genuinely broke"
    )

    return f"""You are {persona.name}, a college student at MIT. Someone is calling you trying to sell you a pen.

## Your Personality
- Your skepticism level is {skepticism_label} — this is how resistant you are to being sold to.
- When someone tries to sell you something, you: {_OBJECTION_STYLE_DESC[persona.objection_style]}
- Your personality traits: {traits_str}

## Your Current Situation
- {_TIME_PRESSURE_DESC[persona.time_pressure]}
- Budget: {budget_label}.
- Context: {persona.context}

## Your Hidden Goal
{_HIDDEN_GOAL_INSTRUCTIONS[persona.hidden_goal]}

## Rules
- Stay in character. You're a real college student on a phone call, not an AI.
- Keep responses SHORT — 1-3 sentences max. This is a phone conversation.
- React to what they actually say. If they make a good point, acknowledge it (even if you're not buying).
- If they reference details about your life that you don't recognize, be confused — "Wait, how do you know that?"
- Use filler words naturally: "uh", "hmm", "I mean", "look".
- Your skepticism level affects how easily you're persuaded, NOT how polite you are.
- Don't break character or mention that this is a simulation."""


class StudentSimulator:
    def __init__(
        self,
        persona: StudentPersona,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
    ):
        self.persona = persona
        self._client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.openai_supervisor_model
        self._system_prompt = build_student_prompt(persona)

    async def respond(self, conversation_history: list[dict]) -> str:
        messages = [{"role": "system", "content": self._system_prompt}]
        for entry in conversation_history:
            # Simulator is "assistant" for its own words, "user" for agent words
            role = "assistant" if entry["role"] == "user" else "user"
            messages.append({"role": role, "content": entry["content"]})
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_completion_tokens=200,
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()
