import pytest

from app.agent.state_machine import ConversationStage, ConversationStateMachine


def test_initial_stage_is_pre_call():
    sm = ConversationStateMachine()
    assert sm.current_stage == ConversationStage.PRE_CALL


def test_valid_transition_pre_call_to_intro():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    assert sm.current_stage == ConversationStage.INTRO


def test_invalid_transition_raises():
    sm = ConversationStateMachine()
    with pytest.raises(ValueError, match="Invalid transition"):
        sm.transition(ConversationStage.CLOSE)


def test_full_happy_path():
    sm = ConversationStateMachine()
    for stage in [
        ConversationStage.INTRO,
        ConversationStage.PITCH,
        ConversationStage.CLOSE,
        ConversationStage.LOGISTICS,
        ConversationStage.WRAP_UP,
    ]:
        sm.transition(stage)
    assert sm.current_stage == ConversationStage.WRAP_UP


def test_objection_loop_back_to_pitch():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    sm.transition(ConversationStage.PITCH)
    sm.transition(ConversationStage.OBJECTION)
    sm.transition(ConversationStage.PITCH)
    assert sm.current_stage == ConversationStage.PITCH


def test_history_tracks_transitions():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    sm.transition(ConversationStage.PITCH)
    assert sm.history == [ConversationStage.PRE_CALL, ConversationStage.INTRO, ConversationStage.PITCH]


def test_to_dict_and_from_dict():
    sm = ConversationStateMachine()
    sm.transition(ConversationStage.INTRO)
    data = sm.to_dict()
    restored = ConversationStateMachine.from_dict(data)
    assert restored.current_stage == ConversationStage.INTRO
    assert restored.history == sm.history
