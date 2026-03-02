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
