from enum import StrEnum


class ConversationStage(StrEnum):
    PRE_CALL = "pre_call"
    INTRO = "intro"
    PITCH = "pitch"
    OBJECTION = "objection"
    CLOSE = "close"
    LOGISTICS = "logistics"
    WRAP_UP = "wrap_up"


# Adjacency list: from_stage -> set of valid next stages
VALID_TRANSITIONS: dict[ConversationStage, set[ConversationStage]] = {
    ConversationStage.PRE_CALL: {ConversationStage.INTRO},
    ConversationStage.INTRO: {ConversationStage.PITCH},
    ConversationStage.PITCH: {ConversationStage.OBJECTION, ConversationStage.CLOSE},
    ConversationStage.OBJECTION: {ConversationStage.PITCH, ConversationStage.CLOSE},
    ConversationStage.CLOSE: {ConversationStage.LOGISTICS, ConversationStage.WRAP_UP},
    ConversationStage.LOGISTICS: {ConversationStage.WRAP_UP},
    ConversationStage.WRAP_UP: set(),
}


class ConversationStateMachine:
    def __init__(self, stage: ConversationStage = ConversationStage.PRE_CALL):
        self._stage = stage
        self._history: list[ConversationStage] = [stage]

    @property
    def current_stage(self) -> ConversationStage:
        return self._stage

    @property
    def history(self) -> list[ConversationStage]:
        return list(self._history)

    def transition(self, next_stage: ConversationStage) -> None:
        valid = VALID_TRANSITIONS.get(self._stage, set())
        if next_stage not in valid:
            raise ValueError(
                f"Invalid transition from {self._stage} to {next_stage}. "
                f"Valid: {valid}"
            )
        self._stage = next_stage
        self._history.append(next_stage)

    def to_dict(self) -> dict:
        return {
            "stage": self._stage.value,
            "history": [s.value for s in self._history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationStateMachine":
        sm = cls(stage=ConversationStage(data["stage"]))
        sm._history = [ConversationStage(s) for s in data["history"]]
        return sm
