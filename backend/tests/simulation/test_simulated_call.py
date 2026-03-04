"""Simulation tests: agent vs. simulated students.

These tests call the OpenAI API and cost real money.
- Preset smoke tests: ~$2.30 (5 calls)
- Random coverage test: ~$9.20 (20 calls)

Run:
    cd backend
    pytest tests/simulation/ -v -s --timeout=300             # all
    pytest tests/simulation/ -k preset -v -s                 # presets only
    pytest tests/simulation/ -k random -v -s --timeout=600   # random only
"""

import asyncio
from pathlib import Path

import pytest

from tests.simulation.call_runner import CallRunner, SimulationResult
from tests.simulation.conftest import SAMPLE_TARGET_ENRICHED
from tests.simulation.judge import ConversationJudge, JudgeVerdict
from tests.simulation.metrics import aggregate_results
from tests.simulation.personas import get_preset, generate_random_personas, PRESETS

REPORT_DIR = str(Path(__file__).parent / "reports")


async def _run_and_judge(
    runner: CallRunner,
    judge: ConversationJudge,
    target_profile: dict,
    persona,
    max_turns: int = 20,
) -> tuple[SimulationResult, JudgeVerdict]:
    result = await runner.run(target_profile=target_profile, persona=persona, max_turns=max_turns)
    verdict = await judge.evaluate(result.transcript, persona)
    return result, verdict


@pytest.fixture
def runner(openai_client):
    return CallRunner(client=openai_client)


@pytest.fixture
def judge(openai_client):
    return ConversationJudge(client=openai_client)


@pytest.mark.parametrize("persona_name", list(PRESETS.keys()))
async def test_preset_persona(runner, judge, persona_name):
    """Run each preset persona and print the full conversation + scores."""
    persona = get_preset(persona_name)
    result, verdict = await _run_and_judge(runner, judge, SAMPLE_TARGET_ENRICHED, persona)

    print(f"\n{'=' * 60}")
    print(f"Persona: {persona_name} (goal: {persona.hidden_goal})")
    print(f"Outcome: {result.outcome} in {result.turns} turns ({result.duration_seconds}s)")
    print(f"{'=' * 60}")
    for entry in result.transcript:
        role = "AGENT" if entry["role"] == "agent" else "STUDENT"
        print(f"  [{role}] {entry['content']}")
    print(f"\nScores: {verdict.score_dict()}")
    print(f"Summary: {verdict.summary}")

    assert verdict.stays_in_character, "Agent broke character"
    assert verdict.no_hallucinated_claims, "Agent hallucinated claims"
    assert not result.max_turns_hit, f"Hit max turns ({result.turns})"


async def test_random_personas(runner, judge):
    """Run 20 random personas, aggregate metrics, save report."""
    personas = generate_random_personas(n=20, seed=42)

    batch_size = 5
    all_pairs: list[tuple[SimulationResult, JudgeVerdict]] = []
    for i in range(0, len(personas), batch_size):
        batch = personas[i : i + batch_size]
        results = await asyncio.gather(
            *[_run_and_judge(runner, judge, SAMPLE_TARGET_ENRICHED, p) for p in batch]
        )
        all_pairs.extend(results)

    report = aggregate_results(all_pairs)
    print(f"\n{report.console_summary()}")
    path = report.save(REPORT_DIR)
    print(f"\nReport saved to: {path}")

    assert report.avg_turns <= 25, f"Avg turns too high: {report.avg_turns}"
