import json

from openai import AsyncOpenAI

from app.agent.prompts.system import OBJECTION_COUNTERS, SUPERVISOR_SYSTEM_PROMPT
from app.agent.state_machine import ConversationStage, ConversationStateMachine
from app.agent.tools import get_tool_schemas
from app.config import settings


class Supervisor:
    def __init__(self, target_profile: dict, state_machine: ConversationStateMachine | None = None):
        self.target_profile = target_profile
        self.state_machine = state_machine or ConversationStateMachine()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._messages: list[dict] = []

    def _build_system_prompt(self) -> str:
        return SUPERVISOR_SYSTEM_PROMPT.format(
            profile=json.dumps(self.target_profile, indent=2),
            stage=self.state_machine.current_stage.value,
            history_summary=", ".join(s.value for s in self.state_machine.history),
        )

    def handle_tool_call(self, tool_name: str, args: dict) -> str:
        if tool_name == "lookup_profile":
            return json.dumps(self.target_profile, indent=2)

        if tool_name == "transition_stage":
            try:
                next_stage = ConversationStage(args["next_stage"])
                self.state_machine.transition(next_stage)
                return f"Transitioned to {next_stage.value}"
            except ValueError as e:
                return f"Error: {e}"

        if tool_name == "get_objection_counters":
            objection_type = args["objection_type"]
            counters = OBJECTION_COUNTERS.get(objection_type, ["Acknowledge their concern and try a different angle."])
            return json.dumps(counters)

        if tool_name == "log_outcome":
            return f"Outcome logged: {args['result']}"

        return f"Unknown tool: {tool_name}"

    async def get_response(self, user_message: str) -> str:
        self._messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model=settings.openai_supervisor_model,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                *self._messages,
            ],
            tools=get_tool_schemas(),
        )

        message = response.choices[0].message

        # Handle tool calls
        while message.tool_calls:
            self._messages.append(message.model_dump())
            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = self.handle_tool_call(tool_call.function.name, args)
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            response = await self._client.chat.completions.create(
                model=settings.openai_supervisor_model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    *self._messages,
                ],
                tools=get_tool_schemas(),
            )
            message = response.choices[0].message

        assistant_text = message.content or ""
        self._messages.append({"role": "assistant", "content": assistant_text})
        return assistant_text
