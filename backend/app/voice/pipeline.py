import json
import logging
from dataclasses import dataclass, field

from app.agent.state_machine import ConversationStateMachine, ConversationStage
from app.agent.supervisor import Supervisor
from app.agent.prompts.system import SUPERVISOR_SYSTEM_PROMPT
from app.services.redis_client import RedisService
from app.voice.realtime import RealtimeSession, SessionConfig

logger = logging.getLogger(__name__)


@dataclass
class CallConfig:
    call_id: str
    target_name: str
    target_profile: dict
    mode: str = "text"  # "text", "browser", "twilio"


REALTIME_INSTRUCTIONS_TEMPLATE = """You are a charming, witty person making a casual call to {name}, an MIT student.
You're selling a pen — but make it fun and personalized. You're not a telemarketer, you're a friend-of-a-friend
who happens to have an amazing pen.

Key info about {name}:
{profile_summary}

Current conversation stage: {stage}

Personality: Confident but not pushy. Funny. Relatable. Think Wolf of Wall Street meets your cool friend.

IMPORTANT: Keep responses concise (1-3 sentences). This is a phone call, not an essay.
If you need to make a strategic decision (which pitch to use, how to handle an objection, when to close),
use the delegate_to_supervisor tool and wait for guidance.
"""


class VoicePipeline:
    def __init__(self, config: CallConfig, redis: RedisService | None = None):
        self.config = config
        self.state_machine = ConversationStateMachine()
        self.supervisor = Supervisor(target_profile=config.target_profile, state_machine=self.state_machine)
        self.redis = redis or RedisService()
        self.is_active = False
        self._realtime: RealtimeSession | None = None
        self._transcript: list[dict] = []

    def _build_realtime_instructions(self) -> str:
        profile_summary = "\n".join(f"- {k}: {v}" for k, v in self.config.target_profile.items() if v)
        return REALTIME_INSTRUCTIONS_TEMPLATE.format(
            name=self.config.target_name,
            profile_summary=profile_summary,
            stage=self.state_machine.current_stage.value,
        )

    async def start(self) -> None:
        self.is_active = True
        self.state_machine.transition(ConversationStage.INTRO)

        await self.redis.publish_event("call.started", {
            "call_id": self.config.call_id,
            "target": self.config.target_name,
            "mode": self.config.mode,
        })

        if self.config.mode == "text":
            await self._run_text_mode()
        else:
            await self._run_voice_mode()

    async def _run_text_mode(self) -> None:
        """Run conversation in text mode (for testing / simulation)."""
        # In text mode, we use the supervisor directly without the Realtime API
        logger.info(f"Starting text-mode call to {self.config.target_name}")
        # The actual text conversation loop is driven externally via process_text_input()

    async def process_text_input(self, user_text: str) -> str:
        """Process a text input and return the agent's response. For text mode only."""
        self._transcript.append({"role": "student", "content": user_text})

        response = await self.supervisor.get_response(user_text)

        self._transcript.append({"role": "agent", "content": response})

        await self.redis.publish_event("transcript.update", {
            "call_id": self.config.call_id,
            "stage": self.state_machine.current_stage.value,
            "message": {"role": "agent", "content": response},
        })

        return response

    async def _run_voice_mode(self) -> None:
        """Run conversation with OpenAI Realtime API (browser or Twilio)."""
        session_config = SessionConfig(
            instructions=self._build_realtime_instructions(),
            tools=[
                {
                    "type": "function",
                    "name": "delegate_to_supervisor",
                    "description": "Delegate a strategic decision to the supervisor model for better reasoning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "What you need the supervisor to decide"},
                            "context": {"type": "string", "description": "Relevant conversation context"},
                        },
                        "required": ["question"],
                    },
                },
            ],
        )
        self._realtime = RealtimeSession(config=session_config)
        await self._realtime.connect()

    async def stop(self) -> None:
        self.is_active = False
        if self._realtime:
            await self._realtime.disconnect()

        await self.redis.publish_event("call.ended", {
            "call_id": self.config.call_id,
            "stage": self.state_machine.current_stage.value,
            "transcript_length": len(self._transcript),
        })

    @property
    def transcript(self) -> list[dict]:
        return list(self._transcript)
