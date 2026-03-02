SUPERVISOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_profile",
            "description": "Fetch the enriched profile for the target person. Returns their name, interests, major, and any other public info gathered during pre-call research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the target person"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transition_stage",
            "description": "Advance the conversation to a new stage. Valid stages: intro, pitch, objection, close, logistics, wrap_up. Only valid transitions are allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "next_stage": {
                        "type": "string",
                        "enum": ["intro", "pitch", "objection", "close", "logistics", "wrap_up"],
                        "description": "The stage to transition to",
                    },
                },
                "required": ["next_stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_objection_counters",
            "description": "Get persuasion tactics to counter a specific type of objection from the target.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objection_type": {
                        "type": "string",
                        "enum": ["too_expensive", "not_interested", "too_busy", "already_have_one", "suspicious"],
                        "description": "The type of objection raised",
                    },
                },
                "required": ["objection_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_outcome",
            "description": "Record the final outcome of the call after wrap-up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "enum": ["sold", "rejected", "callback_requested", "no_answer", "hung_up"],
                        "description": "The outcome of the call",
                    },
                    "notes": {"type": "string", "description": "Any additional notes about the call"},
                },
                "required": ["result"],
            },
        },
    },
]


def get_tool_schemas() -> list[dict]:
    return SUPERVISOR_TOOLS
