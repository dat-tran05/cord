
from app.voice.realtime import RealtimeSession, SessionConfig


def test_session_config_defaults():
    config = SessionConfig(instructions="Sell a pen")
    assert config.voice == "alloy"
    assert config.model == "gpt-realtime-mini"


def test_session_config_to_event():
    config = SessionConfig(instructions="Sell a pen", tools=[{"type": "function", "name": "test"}])
    event = config.to_session_update_event()
    assert event["type"] == "session.update"
    session = event["session"]
    assert session["type"] == "realtime"
    assert session["instructions"] == "Sell a pen"
    assert session["output_modalities"] == ["audio"]
    # GA format: voice is nested under audio.output
    assert session["audio"]["output"]["voice"] == "alloy"
    # GA format: format is an object, not a string
    assert session["audio"]["input"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert session["audio"]["output"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert session["audio"]["input"]["transcription"]["model"] == "gpt-4o-mini-transcribe"
    assert session["audio"]["input"]["transcription"]["language"] == "en"
    assert session["audio"]["input"]["turn_detection"]["type"] == "server_vad"
    assert len(session["tools"]) == 1


def test_create_audio_append_event():
    event = RealtimeSession.create_audio_append_event("dGVzdA==")
    assert event["type"] == "input_audio_buffer.append"
    assert event["audio"] == "dGVzdA=="


def test_create_response_create_event():
    event = RealtimeSession.create_response_event()
    assert event["type"] == "response.create"
