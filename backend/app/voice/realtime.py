import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

import websockets

from app.config import settings

logger = logging.getLogger(__name__)

REALTIME_URL = "wss://api.openai.com/v1/realtime"


@dataclass
class SessionConfig:
    """Configuration for an OpenAI Realtime GA session.

    GA API reference: https://platform.openai.com/docs/api-reference/realtime-client-events
    Key differences from beta:
    - ``format`` is an object ``{"type": "audio/pcm", "rate": 24000}``, not a string.
    - ``output_modalities`` accepts ``["audio"]`` OR ``["text"]``, not both.
    - ``tools`` use a flat format: ``name``, ``description``, and ``parameters``
      sit at the top level alongside ``"type": "function"`` (NOT nested in a
      ``"function"`` wrapper like the Chat Completions REST API).
    """

    instructions: str
    voice: str = "alloy"
    model: str = settings.openai_realtime_model
    input_audio_format: dict = field(
        default_factory=lambda: {"type": "audio/pcm", "rate": 24000}
    )
    output_audio_format: dict = field(
        default_factory=lambda: {"type": "audio/pcm", "rate": 24000}
    )
    tools: list[dict] = field(default_factory=list)
    turn_detection: dict = field(default_factory=lambda: {"type": "server_vad"})
    input_audio_transcription: dict = field(
        default_factory=lambda: {"model": "gpt-4o-mini-transcribe"}
    )

    def to_session_update_event(self) -> dict:
        return {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": ["audio"],
                "instructions": self.instructions,
                "audio": {
                    "input": {
                        "format": self.input_audio_format,
                        "transcription": self.input_audio_transcription,
                        "turn_detection": self.turn_detection,
                    },
                    "output": {
                        "format": self.output_audio_format,
                        "voice": self.voice,
                    },
                },
                "tools": self.tools,
            },
        }


class RealtimeSession:
    def __init__(self, config: SessionConfig, on_tool_call: Callable | None = None):
        self.config = config
        self.on_tool_call = on_tool_call
        self._ws = None
        self._connected = False

    async def connect(self) -> None:
        url = f"{REALTIME_URL}?model={self.config.model}"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
        }
        self._ws = await websockets.connect(url, additional_headers=headers)
        self._connected = True

        # Configure session
        await self._send(self.config.to_session_update_event())
        logger.info("Realtime session connected and configured")

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._connected = False

    async def send_audio(self, audio_b64: str) -> None:
        await self._send(self.create_audio_append_event(audio_b64))

    async def commit_audio(self) -> None:
        await self._send({"type": "input_audio_buffer.commit"})

    async def send_text(self, text: str) -> None:
        """Send a text message (for text-mode testing without audio)."""
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        })
        await self._send(self.create_response_event())

    async def send_tool_result(self, call_id: str, result: str) -> None:
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            },
        })
        await self._send(self.create_response_event())

    async def receive_events(self) -> AsyncIterator[dict]:
        if not self._ws:
            raise RuntimeError("Not connected")
        async for raw in self._ws:
            event = json.loads(raw)
            yield event

    async def _send(self, event: dict) -> None:
        if not self._ws:
            raise RuntimeError("Not connected")
        await self._ws.send(json.dumps(event))

    @staticmethod
    def create_audio_append_event(audio_b64: str) -> dict:
        return {"type": "input_audio_buffer.append", "audio": audio_b64}

    @staticmethod
    def create_response_event() -> dict:
        return {"type": "response.create"}
