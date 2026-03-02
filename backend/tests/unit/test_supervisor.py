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
    result = supervisor.handle_tool_call("get_objection_counters", {"objection_type": "too_expensive"})
    counters = json.loads(result)
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
