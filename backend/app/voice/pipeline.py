import logging
from dataclasses import dataclass

from app.services.redis_client import RedisService
from app.voice.prompt import build_realtime_prompt, pick_voice_for_target
from app.voice.realtime import RealtimeSession, SessionConfig

logger = logging.getLogger(__name__)


@dataclass
class CallConfig:
    call_id: str
    target_name: str
    target_profile: dict
    mode: str = "browser"  # "browser" or "twilio"


class VoicePipeline:
    def __init__(self, config: CallConfig, redis: RedisService | None = None):
        self.config = config
        self.redis = redis or RedisService()
        self.is_active = False
        self._realtime: RealtimeSession | None = None
        self._transcript: list[dict] = []

    def build_prompt(self) -> str:
        """Build the system prompt for the Realtime voice agent."""
        return build_realtime_prompt(
            target_name=self.config.target_name,
            target_profile=self.config.target_profile,
        )

    async def start(self) -> None:
        self.is_active = True

        await self.redis.publish_event("call.started", {
            "call_id": self.config.call_id,
            "target": self.config.target_name,
            "mode": self.config.mode,
        })

        session_config = SessionConfig(
            instructions=self.build_prompt(),
            voice=pick_voice_for_target(self.config.target_name),
        )
        self._realtime = RealtimeSession(config=session_config)
        await self._realtime.connect()

    async def stop(self) -> None:
        self.is_active = False
        if self._realtime:
            await self._realtime.disconnect()

        await self.redis.publish_event("call.ended", {
            "call_id": self.config.call_id,
            "transcript_length": len(self._transcript),
        })

    @property
    def transcript(self) -> list[dict]:
        return list(self._transcript)
