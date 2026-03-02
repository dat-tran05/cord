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
