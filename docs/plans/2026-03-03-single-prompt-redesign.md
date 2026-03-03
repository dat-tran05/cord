# Single-Prompt Voice Agent Redesign

**Date:** 2026-03-03
**Status:** Approved

## Problem

The current dual-model architecture (realtime voice model + GPT-5.2 supervisor with a 7-stage FSM) is over-engineered for selling a pen. The rigid state machine fights the LLM's natural conversational ability, the supervisor adds latency on every strategic decision, and stages like LOGISTICS and WRAP_UP don't map to a casual 2-5 minute pen sale.

## Decision

Replace the dual-model + FSM architecture with a single realtime voice model using one comprehensive prompt. No state machine, no supervisor, no tool calls. Post-call AI analysis remains on the final transcript.

## Architecture

```
Browser audio (PCM16 24kHz via WebSocket)
    |
ws_voice.py -- bidirectional audio bridge (no tool interception)
    |
OpenAI Realtime API (gpt-realtime-mini, single comprehensive prompt)
    |
Voice back to browser
    | (after call ends)
Full transcript -> GPT analysis endpoint
```

## What Gets Removed

- `app/agent/state_machine.py` -- 7-stage FSM and transition validation
- `app/agent/supervisor.py` -- GPT-5.2 supervisor and tool-calling loop
- `app/agent/tools.py` -- 4 supervisor tools (lookup_profile, transition_stage, get_objection_counters, log_outcome)
- `app/agent/prompts/system.py` -- supervisor prompt and hardcoded objection counters
- `delegate_to_supervisor` tool from realtime session config
- Related unit tests: test_state_machine.py, test_supervisor.py, test_tools.py

## What Gets Simplified

### pipeline.py
- Remove ConversationStateMachine and Supervisor dependencies
- Build one comprehensive prompt with target profile injected
- Manage realtime session lifecycle only

### ws_voice.py
- Remove supervisor delegation handling (no tool calls to intercept)
- Becomes a clean audio passthrough bridge between browser and OpenAI

## The Prompt

One system prompt given to the realtime model covers:

1. **Identity** -- personality, tone (Wolf of Wall Street meets your cool friend), confidence without pushiness
2. **Target context** -- name, major, interests (injected from profile data)
3. **Sales strategy** -- how to open naturally, pitch angles, personalization based on background
4. **Objection handling** -- behavioral guidelines for common pushbacks (too expensive, not interested, too busy, already have one, suspicious), woven into the prompt not retrieved via tools
5. **Closing instincts** -- when to push, when to back off, graceful exit
6. **Guardrails** -- 1-3 sentence responses, stay conversational, respect firm refusals

## Testing

Remove tests for state_machine, supervisor, and tools. New/updated tests cover:
- Prompt building (profile injection)
- Pipeline lifecycle (start/stop, event publishing)
- WebSocket bridge (audio forwarding)

## Future Extensibility

If the product becomes more complex (e.g., booking flights, handling payments), tool calls and prompt-switching (Approach 2: prompt graph via session.update) can be added without rearchitecting. The single-prompt approach is the simplest starting point that works for the current use case.
