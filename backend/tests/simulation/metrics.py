from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from tests.simulation.call_runner import SimulationResult
from tests.simulation.judge import JudgeVerdict

_SCORE_NAMES = [
    "objection_handling", "rapport_building", "naturalness",
    "pushiness", "closing_technique", "personalization",
]


@dataclass
class SimulationReport:
    total_calls: int = 0
    sale_rate: float = 0.0
    avg_turns: float = 0.0
    avg_scores: dict[str, float] = field(default_factory=dict)
    score_distributions: dict[str, list[int]] = field(default_factory=dict)
    by_persona_type: dict[str, dict] = field(default_factory=dict)
    safety_violations: list[dict] = field(default_factory=list)
    outcomes: dict[str, int] = field(default_factory=dict)

    def save(self, directory: str) -> str:
        Path(directory).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(directory) / f"sim_report_{ts}.json"
        path.write_text(json.dumps(self._to_dict(), indent=2))
        return str(path)

    def console_summary(self) -> str:
        lines = [
            "=== Simulation Report ===",
            f"Total calls: {self.total_calls}",
            f"Sale rate: {self.sale_rate:.1%}",
            f"Avg turns: {self.avg_turns:.1f}",
            "",
            "--- Avg Scores ---",
        ]
        for name, val in self.avg_scores.items():
            lines.append(f"  {name}: {val:.1f}/10")
        lines.append("")
        lines.append("--- Outcomes ---")
        for outcome, count in self.outcomes.items():
            lines.append(f"  {outcome}: {count}")
        if self.safety_violations:
            lines.append(f"\n!!! {len(self.safety_violations)} safety violation(s) !!!")
        lines.append("")
        lines.append("--- By Persona ---")
        for persona, stats in self.by_persona_type.items():
            lines.append(f"  {persona}: sale_rate={stats['sale_rate']:.0%}, calls={stats['count']}")
        return "\n".join(lines)

    def _to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "sale_rate": self.sale_rate,
            "avg_turns": self.avg_turns,
            "avg_scores": self.avg_scores,
            "score_distributions": self.score_distributions,
            "by_persona_type": self.by_persona_type,
            "safety_violations": self.safety_violations,
            "outcomes": self.outcomes,
        }


def aggregate_results(
    pairs: list[tuple[SimulationResult, JudgeVerdict]],
) -> SimulationReport:
    if not pairs:
        return SimulationReport()

    report = SimulationReport(total_calls=len(pairs))

    all_scores: dict[str, list[int]] = {name: [] for name in _SCORE_NAMES}
    sales = 0
    turns_list: list[int] = []
    outcomes: dict[str, int] = {}
    persona_data: dict[str, list[tuple[SimulationResult, JudgeVerdict]]] = {}

    for result, verdict in pairs:
        outcomes[result.outcome] = outcomes.get(result.outcome, 0) + 1
        turns_list.append(result.turns)
        if verdict.sale_completed:
            sales += 1

        score_dict = verdict.score_dict()
        for name in _SCORE_NAMES:
            all_scores[name].append(score_dict[name])

        if not verdict.stays_in_character or not verdict.no_hallucinated_claims or not verdict.respects_firm_refusal:
            report.safety_violations.append({
                "persona": result.persona_name,
                "stays_in_character": verdict.stays_in_character,
                "no_hallucinated_claims": verdict.no_hallucinated_claims,
                "respects_firm_refusal": verdict.respects_firm_refusal,
                "summary": verdict.summary,
            })

        persona_data.setdefault(result.persona_name, []).append((result, verdict))

    report.sale_rate = sales / len(pairs)
    report.avg_turns = sum(turns_list) / len(turns_list)
    report.outcomes = outcomes
    report.score_distributions = all_scores
    report.avg_scores = {name: sum(vals) / len(vals) for name, vals in all_scores.items()}

    for persona_name, persona_pairs in persona_data.items():
        p_sales = sum(1 for _, v in persona_pairs if v.sale_completed)
        report.by_persona_type[persona_name] = {
            "count": len(persona_pairs),
            "sale_rate": p_sales / len(persona_pairs),
        }

    return report
