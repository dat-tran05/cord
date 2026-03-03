import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.voice.pipeline import VoicePipeline, CallConfig


def _make_config(**overrides):
    defaults = {
        "call_id": "call-1",
        "target_name": "Alex Chen",
        "target_profile": {"name": "Alex Chen", "major": "CS", "interests": "robotics"},
    }
    defaults.update(overrides)
    return CallConfig(**defaults)


def test_call_config_creation():
    config = _make_config()
    assert config.call_id == "call-1"
    assert config.target_name == "Alex Chen"
    assert config.mode == "browser"  # default


def test_call_config_mode_override():
    config = _make_config(mode="twilio")
    assert config.mode == "twilio"


def test_pipeline_initial_state():
    config = _make_config()
    pipeline = VoicePipeline(config)
    assert pipeline.is_active is False
    assert pipeline.transcript == []
    assert pipeline._realtime is None


def test_build_prompt_contains_target_name():
    config = _make_config()
    pipeline = VoicePipeline(config)
    prompt = pipeline.build_prompt()
    assert "Alex Chen" in prompt


def test_build_prompt_contains_profile_info():
    config = _make_config()
    pipeline = VoicePipeline(config)
    prompt = pipeline.build_prompt()
    assert "CS" in prompt
    assert "robotics" in prompt


def test_build_prompt_contains_objection_counters():
    config = _make_config()
    pipeline = VoicePipeline(config)
    prompt = pipeline.build_prompt()
    assert "Objection Counters" in prompt


@pytest.mark.asyncio
async def test_start_activates_pipeline():
    config = _make_config()
    mock_redis = MagicMock()
    mock_redis.publish_event = AsyncMock()
    pipeline = VoicePipeline(config, redis=mock_redis)

    with patch("app.voice.pipeline.RealtimeSession") as MockRT:
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        MockRT.return_value = mock_session

        await pipeline.start()

    assert pipeline.is_active is True
    assert pipeline._realtime is mock_session
    mock_session.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_publishes_event():
    config = _make_config()
    mock_redis = MagicMock()
    mock_redis.publish_event = AsyncMock()
    pipeline = VoicePipeline(config, redis=mock_redis)

    with patch("app.voice.pipeline.RealtimeSession") as MockRT:
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        MockRT.return_value = mock_session

        await pipeline.start()

    mock_redis.publish_event.assert_any_call("call.started", {
        "call_id": "call-1",
        "target": "Alex Chen",
        "mode": "browser",
    })


@pytest.mark.asyncio
async def test_start_creates_session_with_prompt():
    config = _make_config()
    mock_redis = MagicMock()
    mock_redis.publish_event = AsyncMock()
    pipeline = VoicePipeline(config, redis=mock_redis)

    with patch("app.voice.pipeline.RealtimeSession") as MockRT:
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        MockRT.return_value = mock_session

        await pipeline.start()

    session_config = MockRT.call_args[1]["config"] if MockRT.call_args[1] else MockRT.call_args[0][0]
    assert "Alex Chen" in session_config.instructions
    assert session_config.tools == []  # no delegate_to_supervisor tool


@pytest.mark.asyncio
async def test_stop_deactivates_pipeline():
    config = _make_config()
    mock_redis = MagicMock()
    mock_redis.publish_event = AsyncMock()
    pipeline = VoicePipeline(config, redis=mock_redis)

    mock_realtime = MagicMock()
    mock_realtime.disconnect = AsyncMock()
    pipeline._realtime = mock_realtime
    pipeline.is_active = True

    await pipeline.stop()

    assert pipeline.is_active is False
    mock_realtime.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_publishes_event():
    config = _make_config()
    mock_redis = MagicMock()
    mock_redis.publish_event = AsyncMock()
    pipeline = VoicePipeline(config, redis=mock_redis)
    pipeline.is_active = True

    await pipeline.stop()

    mock_redis.publish_event.assert_called_once_with("call.ended", {
        "call_id": "call-1",
        "transcript_length": 0,
    })


@pytest.mark.asyncio
async def test_stop_without_realtime_session():
    """Stop should work even if start() was never called."""
    config = _make_config()
    mock_redis = MagicMock()
    mock_redis.publish_event = AsyncMock()
    pipeline = VoicePipeline(config, redis=mock_redis)

    await pipeline.stop()  # should not raise

    assert pipeline.is_active is False


def test_transcript_returns_copy():
    config = _make_config()
    pipeline = VoicePipeline(config)
    pipeline._transcript.append({"role": "agent", "content": "Hello!"})

    transcript = pipeline.transcript
    assert len(transcript) == 1
    assert transcript is not pipeline._transcript  # should be a copy
