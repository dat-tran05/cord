from __future__ import annotations

import random
from dataclasses import dataclass, field

OBJECTION_STYLES = ("polite_decline", "aggressive", "passive", "curious_but_broke")
TIME_PRESSURES = ("none", "late_for_class", "walking_with_friends")
HIDDEN_GOALS = ("buy", "refuse", "stall", "agree_then_back_out")

_TRAIT_POOL = [
    "analytical", "impulsive", "busy", "frugal", "social",
    "introverted", "skeptical", "enthusiastic", "distracted", "competitive",
]

_NAMES = [
    "Alex Chen", "Priya Sharma", "Marcus Johnson", "Sofia Rodriguez",
    "Wei Zhang", "Aisha Patel", "Jordan Kim", "Emma Okafor",
    "Liam Nakamura", "Zara Hassan",
]


@dataclass(frozen=True)
class StudentPersona:
    name: str
    skepticism: float
    objection_style: str
    time_pressure: str
    budget_sensitivity: float
    personality_traits: list[str] = field(default_factory=list)
    hidden_goal: str = "refuse"
    context: str = ""


PRESETS: dict[str, StudentPersona] = {
    "easy_sell": StudentPersona(
        name="Alex Chen",
        skepticism=0.2,
        objection_style="curious_but_broke",
        time_pressure="none",
        budget_sensitivity=0.3,
        personality_traits=["enthusiastic", "impulsive"],
        hidden_goal="buy",
        context="Relaxing in dorm after class, bored and chatty.",
    ),
    "hard_sell": StudentPersona(
        name="Marcus Johnson",
        skepticism=0.9,
        objection_style="aggressive",
        time_pressure="none",
        budget_sensitivity=0.5,
        personality_traits=["analytical", "skeptical", "competitive"],
        hidden_goal="refuse",
        context="Studying for finals, annoyed at the interruption.",
    ),
    "busy_no_time": StudentPersona(
        name="Priya Sharma",
        skepticism=0.5,
        objection_style="passive",
        time_pressure="late_for_class",
        budget_sensitivity=0.4,
        personality_traits=["busy", "social"],
        hidden_goal="stall",
        context="Walking to lecture, class starts in 3 minutes.",
    ),
    "curious_but_broke": StudentPersona(
        name="Sofia Rodriguez",
        skepticism=0.4,
        objection_style="polite_decline",
        time_pressure="none",
        budget_sensitivity=0.9,
        personality_traits=["enthusiastic", "frugal"],
        hidden_goal="stall",
        context="In the dining hall, interested but genuinely broke.",
    ),
    "agree_then_bail": StudentPersona(
        name="Jordan Kim",
        skepticism=0.3,
        objection_style="polite_decline",
        time_pressure="none",
        budget_sensitivity=0.4,
        personality_traits=["social", "distracted"],
        hidden_goal="agree_then_back_out",
        context="Hanging out in common room, easily swayed but flaky.",
    ),
}


def get_preset(name: str) -> StudentPersona:
    return PRESETS[name]


def generate_random_personas(n: int, seed: int | None = None) -> list[StudentPersona]:
    rng = random.Random(seed)
    personas = []
    for _ in range(n):
        traits = rng.sample(_TRAIT_POOL, k=rng.randint(1, 3))
        personas.append(
            StudentPersona(
                name=rng.choice(_NAMES),
                skepticism=round(rng.uniform(0.1, 0.95), 2),
                objection_style=rng.choice(OBJECTION_STYLES),
                time_pressure=rng.choice(TIME_PRESSURES),
                budget_sensitivity=round(rng.uniform(0.1, 0.95), 2),
                personality_traits=traits,
                hidden_goal=rng.choice(HIDDEN_GOALS),
                context=rng.choice([
                    "Just finished a problem set, decompressing.",
                    "Walking across campus between classes.",
                    "In the library, trying to focus.",
                    "At a coffee shop, relaxed and chatty.",
                    "In their dorm room, watching YouTube.",
                ]),
            )
        )
    return personas
