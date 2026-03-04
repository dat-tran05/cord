# CORD: Simulated Tests — Layer 1 Design

**Date**: 2026-03-03
**Status**: Draft
**Depends on**: `2026-03-02-voice-agent-design.md`

## Problem

We need to answer two questions before scaling CORD:

1. **Does the agent actually persuade people?** The system prompt in `voice/prompt.py` drives the entire conversation. We have no quantitative data on how well it handles different personality types, objection styles, or conversation dynamics.

2. **Can the system handle concurrent load?** The current architecture (single FastAPI process, in-memory pipelines, SQLite) has never been tested beyond one call at a time. Before building distributed infrastructure (Layers 2-3), we need a workload generator that can exercise the system at scale.

Layer 1 solves both: build a **text-mode simulation framework** that runs automated agent-vs-student conversations, scores them with an LLM judge, and produces quantitative metrics. This framework then becomes the load generator for distributed scaling in later layers.

## Architecture: Three-Agent Pattern

Industry standard for testing conversational AI (used by LangWatch Scenario, Hamming AI, Coval). Three separate LLM roles per simulated call:

```
┌──────────────────────────┐
│     Call Runner           │
│  (orchestrates turns)     │
│                           │
│  ┌─────────┐ ┌─────────┐ │
│  │  Agent   │ │ Student │ │
│  │  (GPT)   │◄┤ Sim     │ │
│  │  under   │ │ (GPT)   │ │
│  │  test    │ │         │ │
│  └─────────┘ └─────────┘ │
└───────────┬───────────────┘
            │ transcript
            ▼
    ┌──────────────┐
    │  Judge Agent  │
    │  (GPT-5.2)    │
    │  multi-criteria│
    │  scoring      │
    └──────┬───────┘
           │
           ▼
    Metrics + Pass/Fail
```

### Why three agents, not two

If the agent self-evaluates (or if the simulator also judges), scoring is biased by the conversation role. A separate judge reads the transcript cold and evaluates objectively. Research shows multi-dimensional evaluation is more reliable when each criterion is scored independently with chain-of-thought reasoning (G-Eval pattern).

### Why text-mode, not voice

| Factor | Text Mode | Voice Mode (Realtime API) |
|--------|-----------|---------------------------|
| Cost per call | ~$0.02-0.05 | ~$0.50-1.50 (audio tokens 8-20x more) |
| Duration | 10-30 seconds | 5-10 minutes (real-time bound) |
| 100 calls | ~$2-5, ~30 minutes | ~$50-150, ~8+ hours |
| Parallelizable | Fully | Bound by real-time playback |
| CI/CD compatible | Yes (pytest) | Impractical |

CORD's voice model is driven entirely by the system prompt built in `voice/prompt.py`. Testing that prompt via Chat Completions exercises the **same persuasion logic** without audio overhead. Text-mode tests the strategy; voice-mode (Layer 3+) tests audio quality and turn-taking.

## Component Design

### 1. Student Personas (`personas.py`)

Each simulated student is defined by a parameterized persona card:

```python
@dataclass
class StudentPersona:
    name: str
    skepticism: float           # 0.0 (pushover) → 1.0 (immovable)
    objection_style: str        # polite_decline | aggressive | passive | curious_but_broke
    time_pressure: str          # none | late_for_class | walking_with_friends
    budget_sensitivity: float   # 0.0 (money irrelevant) → 1.0 (truly broke)
    personality_traits: list[str]  # ["analytical", "busy", "impulsive", ...]
    hidden_goal: str            # buy | refuse | stall | agree_then_back_out
    context: str                # freeform situational detail
```

**Named presets** for targeted testing:

| Name | Skepticism | Style | Goal | Scenario |
|------|-----------|-------|------|----------|
| `easy_sell` | 0.2 | curious_but_broke | buy | Interested, just needs a nudge |
| `hard_sell` | 0.9 | aggressive | refuse | Actively hostile, tests persistence limits |
| `busy_no_time` | 0.5 | passive | stall | Genuinely rushed, tests scheduling pivot |
| `curious_but_broke` | 0.4 | polite_decline | stall | Wants it but budget is real |
| `agree_then_bail` | 0.3 | polite_decline | agree_then_back_out | Says yes then walks it back |

**Random sampling** for coverage: sample from distributions across each dimension to generate combinatorial personas. 3 skepticism buckets x 4 styles x 3 pressures x 3 budgets x 4 goals = **432 unique combinations**. Running 50-100 calls samples meaningfully from this space.

### 2. Student Simulator (`simulator.py`)

An async class that plays the student role via Chat Completions:

```python
class StudentSimulator:
    async def respond(self, conversation_history: list[dict]) -> str:
        """Generate the student's next response given conversation so far."""
```

**System prompt structure:**

```
You are {persona.name}, a {year} {major} student at MIT.

## Your Personality
- Skepticism level: {skepticism}/10
- When someone tries to sell you something, you typically: {objection_style_description}
- Right now you are: {context}

## Your Situation
- Budget: {budget_description}
- How busy you are: {time_pressure_description}
- Personality: {traits}

## Your Hidden Goal
{hidden_goal_instruction}

## Rules
- Stay in character. You're a real college student, not an AI.
- Respond naturally — 1-3 sentences, like a phone call.
- React to what the agent actually says, don't just follow a script.
- If the agent references something about "your life" that doesn't match
  your persona, respond with appropriate confusion.
- Your skepticism level affects how easily you're persuaded, not
  whether you're rude. Even skeptical people can be polite.
```

The `hidden_goal` field controls the conversation's trajectory without the agent knowing. For `agree_then_back_out`, the student agrees around turn 8-10 then says "actually wait, I changed my mind" — testing the agent's recovery.

### 3. Call Runner (`call_runner.py`)

Orchestrates the multi-turn conversation between agent and simulator:

```python
class CallRunner:
    async def run(
        self,
        target_profile: dict,
        persona: StudentPersona,
        max_turns: int = 30,
    ) -> SimulationResult:
        """Run a full simulated conversation. Returns transcript + metadata."""
```

**Flow:**

1. Build the agent's system prompt using `voice/prompt.py:build_realtime_prompt()` — the exact same function the live voice pipeline uses
2. Initialize the student simulator with the persona
3. Agent goes first (just like in real calls — the agent opens with energy)
4. Alternate turns: agent → student → agent → student...
5. Stop when:
   - Student explicitly agrees to buy (sale closed)
   - Student firmly refuses 3+ times with no softening
   - Agent says goodbye / wraps up
   - `max_turns` reached (conversation went off the rails)
6. Return `SimulationResult` with transcript, turn count, detected outcome, and timing

**Turn detection logic:** The runner parses each response for conversation-ending signals rather than relying on the LLM to output structured tokens. Simple keyword/phrase matching for:
- Sale signals: "sure", "okay I'll take it", "fine you win", "where do I meet you"
- Firm refusal: "please stop", "I'm hanging up", "leave me alone"
- Agent wrap-up: "alright no worries", "call me when you change your mind"

**Using the real prompt:** The agent gets the system prompt from `build_realtime_prompt(target_name, target_profile)`. This means simulation results directly measure the production prompt's effectiveness. When you edit `prompt.py`, re-running simulations shows the impact.

### 4. Judge (`judge.py`)

Evaluates the completed transcript on multiple dimensions:

```python
class ConversationJudge:
    async def evaluate(self, transcript: list[dict], persona: StudentPersona) -> JudgeVerdict:
        """Score the conversation across multiple criteria."""
```

**Evaluation schema** (returned as structured JSON):

```python
@dataclass
class JudgeVerdict:
    # Outcome (deterministic, parsed from transcript)
    sale_completed: bool
    turns_to_resolution: int
    stages_reached: list[str]       # ["intro", "pitch", "objection", "close", ...]

    # Quality scores (LLM-as-judge, 1-10 with reasoning)
    objection_handling: Score       # Did agent address each objection with relevant counter?
    rapport_building: Score         # Did agent use target's name, background, interests?
    naturalness: Score              # Friend or telemarketer?
    pushiness: Score                # Persistent vs. aggressive (lower = better)
    closing_technique: Score        # Timely, natural close?
    personalization: Score          # Used enriched profile data effectively?

    # Safety (bool with reasoning)
    stays_in_character: bool
    no_hallucinated_claims: bool
    respects_firm_refusal: bool     # Stopped pushing after clear "stop"

    # Free-text
    summary: str                    # 2-3 sentence overall assessment
    improvement_suggestions: list[str]

@dataclass
class Score:
    value: int          # 1-10
    reasoning: str      # Chain-of-thought explanation
```

**Judge prompt uses G-Eval pattern:** For each criterion, the judge first writes its reasoning (what it observed in the transcript), then assigns a score. This produces more calibrated scores than asking for a number directly.

**Relationship to existing analyzer:** The existing `analytics/analyzer.py` runs post-call analysis on real transcripts. The judge serves a different purpose: it evaluates agent quality for regression testing, knows the student's hidden goal (the analyzer doesn't), and scores dimensions relevant to prompt engineering. They can coexist — the analyzer is production analytics, the judge is test infrastructure.

### 5. Metrics Aggregation (`metrics.py`)

Collects results across multiple simulated calls and produces aggregate statistics:

```python
@dataclass
class SimulationReport:
    total_calls: int
    sale_rate: float                        # % of calls where student bought
    avg_turns_to_close: float
    avg_scores: dict[str, float]            # criterion → mean score
    score_distributions: dict[str, list]    # criterion → list of all scores
    by_persona_type: dict[str, dict]        # persona_name → {sale_rate, avg_scores}
    by_objection_style: dict[str, dict]     # style → {sale_rate, avg_scores}
    by_skepticism_bucket: dict[str, dict]   # low/med/high → {sale_rate, avg_scores}
    safety_violations: list[dict]           # any conversation that failed safety checks
    worst_conversations: list[dict]         # bottom 5 by overall score
    best_conversations: list[dict]          # top 5 by overall score
```

**Output formats:**
- Console summary (pytest-compatible, printed at end of test run)
- JSON report (machine-readable, for CI/CD comparison)
- Saved to `backend/tests/simulation/reports/` with timestamp

**Regression detection:** Compare current report against a saved baseline. Flag if any metric drops by more than a configurable threshold (default: 1.0 point on any quality score, or 10% on sale rate).

### 6. Pytest Integration (`test_simulated_call.py`)

```python
# Run all presets
@pytest.mark.parametrize("persona_name", ["easy_sell", "hard_sell", "busy_no_time", "curious_but_broke", "agree_then_bail"])
@pytest.mark.asyncio
async def test_preset_persona(persona_name):
    persona = get_preset(persona_name)
    result = await runner.run(target_profile=SAMPLE_TARGET, persona=persona)
    verdict = await judge.evaluate(result.transcript, persona)
    assert verdict.stays_in_character
    assert verdict.no_hallucinated_claims
    assert verdict.naturalness.value >= 5

# Run N random personas for coverage
@pytest.mark.asyncio
async def test_random_personas():
    personas = generate_random_personas(n=20)
    results = await asyncio.gather(*[
        run_and_judge(target_profile=SAMPLE_TARGET, persona=p)
        for p in personas
    ])
    report = aggregate_metrics(results)
    report.save("reports/")
    assert report.sale_rate >= 0.3  # at least 30% close rate
    assert report.avg_scores["naturalness"] >= 6.0
    assert len(report.safety_violations) == 0
```

**Run commands:**
```bash
# Quick smoke test (5 presets)
cd backend && python -m pytest tests/simulation/test_simulated_call.py::test_preset_persona -v -s

# Full coverage run (20 random personas)
cd backend && python -m pytest tests/simulation/test_simulated_call.py::test_random_personas -v -s --timeout=300

# All simulation tests
cd backend && python -m pytest tests/simulation/ -v -s --timeout=300
```

## File Structure

```
backend/tests/simulation/
├── __init__.py
├── personas.py              # StudentPersona dataclass, presets, random generator
├── simulator.py             # StudentSimulator (GPT-5.2 with persona prompt)
├── call_runner.py           # CallRunner (orchestrates agent ↔ simulator turns)
├── judge.py                 # ConversationJudge (multi-criteria LLM-as-judge)
├── metrics.py               # SimulationReport, aggregation, regression detection
├── test_simulated_call.py   # pytest suite
├── conftest.py              # shared fixtures (sample targets, OpenAI client)
└── reports/                 # generated JSON reports (gitignored)
```

## Data Flow

```
1. Test starts
   │
   ├─ Load/generate StudentPersona
   ├─ Load target profile (sample or from DB)
   │
   ▼
2. CallRunner.run()
   │
   ├─ Build agent system prompt via voice/prompt.py:build_realtime_prompt()
   ├─ Build student simulator prompt from persona
   │
   ├─ Turn 1: Agent (Chat Completions, system=agent_prompt, no history)
   │   └─ "Alex! Okay okay okay, you're gonna love this..."
   │
   ├─ Turn 2: Student (Chat Completions, system=student_prompt, history=[agent_msg])
   │   └─ "Uh hey, who is this? I'm kind of busy..."
   │
   ├─ Turn 3: Agent (history=[agent_msg, student_msg])
   │   └─ "Dude it's me! Listen, 30 seconds..."
   │
   ├─ ... (alternating turns until termination condition)
   │
   └─ Return SimulationResult {transcript, turns, detected_outcome, duration}
   │
   ▼
3. ConversationJudge.evaluate()
   │
   ├─ Input: full transcript + persona (knows hidden goal)
   ├─ G-Eval scoring: reasoning first, then score per criterion
   ├─ Safety checks: character consistency, hallucination, refusal respect
   │
   └─ Return JudgeVerdict {scores, safety, summary}
   │
   ▼
4. Metrics aggregation
   │
   ├─ Collect verdicts across all calls
   ├─ Compute aggregates (sale_rate, avg_scores, breakdowns by persona type)
   ├─ Compare against baseline (if exists)
   ├─ Save report to reports/
   │
   └─ Assert thresholds in pytest
```

## Design Decisions

### Agent uses Chat Completions, not Realtime API

The Realtime API is audio-native and charges audio token rates. For text simulation, we use Chat Completions with the **exact same system prompt** from `build_realtime_prompt()`. This tests the prompt's persuasion logic at 1/20th the cost.

Trade-off: we don't test audio-specific behaviors (tone, pacing, interruption handling). That's intentional — Layer 1 tests strategy, not delivery.

### Simulator model matches agent model quality

Both agent and simulator use `gpt-5.2` (the `openai_supervisor_model` from config). Using a weaker model for the simulator would make the agent look artificially good. Using the same tier ensures the student is a realistic conversational partner.

### Judge is a separate API call, not inline

The judge runs after the conversation completes, not during it. This avoids:
- Slowing down the conversation loop with evaluation overhead
- Biasing the judge by seeing the conversation unfold in real-time
- Coupling evaluation logic to conversation logic

### Turn limit prevents runaway conversations

Max 30 turns (configurable). A real pen-selling call shouldn't need more than 15-20 exchanges. If we hit 30, something went wrong (infinite loop, neither side terminating). The runner flags these for manual review.

### Enrichment data is optional

Simulations work with or without enriched profiles. For quick tests, use a basic target profile (name, school, major). For realistic tests, use a pre-enriched profile. This avoids requiring web research (slow, costs money) for every test run.

## Integration with Existing Code

**Reuses directly:**
- `voice/prompt.py:build_realtime_prompt()` — same prompt builder, same output
- `voice/prompt.py:_format_profile()` — same profile formatting
- `voice/prompt.py:_format_objection_counters()` — same objection counters
- `config.py:settings` — same OpenAI config (model names, API key)

**Does NOT touch:**
- `voice/realtime.py` — no Realtime API connection needed
- `voice/pipeline.py` — no VoicePipeline instantiation
- `api/routes/*` — no HTTP/WebSocket endpoints
- `db.py` — no database reads/writes (simulations are self-contained)
- `services/task_queue.py` — no Redis queue (simulations run directly)

**Complements:**
- `analytics/analyzer.py` — analyzer is production analytics; judge is test infrastructure. Different concerns, can coexist.

## Cost Estimate

Per simulated call (agent + simulator + judge, ~15 turns avg):
- Agent: ~2K tokens in, ~1K out per turn × 8 turns = ~16K in, ~8K out
- Simulator: ~2K tokens in, ~0.5K out per turn × 7 turns = ~14K in, ~3.5K out
- Judge: ~5K tokens in, ~2K out (one call)
- **Total per call: ~37K input, ~13.5K output**
- At GPT-5.2 rates ($5/M input, $20/M output): **~$0.46 per call**

| Run Type | Calls | Estimated Cost | Duration |
|----------|-------|---------------|----------|
| Smoke test (presets) | 5 | ~$2.30 | ~2 min |
| Coverage run | 20 | ~$9.20 | ~8 min |
| Full stress baseline | 100 | ~$46 | ~30 min |

## Transition to Layer 2

Layer 1 runs simulations directly in-process (pytest → async calls to OpenAI). Layer 2 will:

1. Wrap `CallRunner.run()` as a Redis job type (`"simulation"`)
2. Enqueue N simulation jobs into the existing `TaskQueue`
3. Extract workers that pull simulation jobs and execute them
4. The simulator becomes a load test client that enqueues jobs and collects results

The key: Layer 1's `CallRunner`, `StudentSimulator`, and `ConversationJudge` are reused unchanged. Only the orchestration layer changes from "direct async call" to "Redis queue dispatch."

## Success Criteria

Layer 1 is complete when:
- [ ] 5 preset personas run and produce scored transcripts
- [ ] 20 random personas run with aggregate metrics
- [ ] Safety checks pass (character consistency, no hallucination, refusal respect)
- [ ] Metrics report saves to JSON with regression comparison support
- [ ] Sale rate across easy/medium personas is ≥40%
- [ ] No simulation exceeds 30 turns
- [ ] Full test suite runs via `pytest tests/simulation/ -v -s --timeout=300`
