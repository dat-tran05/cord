"""Tests for the single-prompt builder module."""


from app.voice.prompt import build_realtime_prompt, _format_profile, _format_objection_counters


class TestFormatProfile:
    def test_formats_non_empty_values(self):
        profile = {"name": "Alex Chen", "major": "Computer Science", "dorm": "Baker House"}
        result = _format_profile(profile)
        assert "- name: Alex Chen" in result
        assert "- major: Computer Science" in result
        assert "- dorm: Baker House" in result

    def test_skips_empty_values(self):
        profile = {"name": "Alex Chen", "major": "", "interests": None}
        result = _format_profile(profile)
        assert "- name: Alex Chen" in result
        assert "major" not in result
        assert "interests" not in result

    def test_empty_profile(self):
        result = _format_profile({})
        assert result == "- No profile information available"

    def test_skips_internal_keys(self):
        profile = {"name": "Alex", "id": "abc123", "enrichment_status": "enriched", "created_at": "2026-01-01"}
        result = _format_profile(profile)
        assert "- name: Alex" in result
        assert "abc123" not in result
        assert "enrichment_status" not in result
        assert "created_at" not in result

    def test_formats_lists_as_comma_separated(self):
        profile = {"interests": ["robotics", "coffee", "chess"]}
        result = _format_profile(profile)
        assert "- interests: robotics, coffee, chess" in result

    def test_includes_enriched_profile(self):
        profile = {
            "name": "Alex",
            "enriched_profile": {
                "talking_points": ["Ask about RoboCup team", "Coffee passion"],
                "rapport_hooks": ["Coffee enthusiasm"],
                "personalized_pitch_angles": ["The engineer's pen"],
                "anticipated_objections": ["Too busy with research"],
            },
        }
        result = _format_profile(profile)
        assert "Research & Talking Points" in result
        assert "Ask about RoboCup team" in result
        assert "Coffee enthusiasm" in result
        assert "engineer's pen" in result

    def test_enriched_profile_none_not_shown(self):
        profile = {"name": "Alex", "enriched_profile": None}
        result = _format_profile(profile)
        assert "Research & Talking Points" not in result

    def test_enriched_profile_empty_not_shown(self):
        profile = {"name": "Alex", "enriched_profile": {}}
        result = _format_profile(profile)
        assert "Research & Talking Points" not in result


class TestFormatObjectionCounters:
    def test_includes_all_objection_types(self):
        result = _format_objection_counters()
        assert "Too expensive" in result
        assert "Not interested" in result
        assert "Too busy" in result
        assert "Already have a pen" in result
        assert "suspicious" in result.lower()


class TestBuildRealtimePrompt:
    """Core tests for the build_realtime_prompt function."""

    def test_includes_target_name(self):
        prompt = build_realtime_prompt("Alex Chen", {"name": "Alex Chen"})
        assert "Alex Chen" in prompt

    def test_includes_profile_info(self):
        profile = {
            "name": "Jordan Lee",
            "major": "Electrical Engineering",
            "interests": "robotics, chess",
            "dorm": "Simmons Hall",
        }
        prompt = build_realtime_prompt("Jordan Lee", profile)
        assert "Electrical Engineering" in prompt
        assert "robotics, chess" in prompt
        assert "Simmons Hall" in prompt

    def test_includes_conversation_stages(self):
        prompt = build_realtime_prompt("Alex", {"name": "Alex"})
        assert "INTRO" in prompt
        assert "PITCH" in prompt
        assert "OBJECTION" in prompt
        assert "CLOSE" in prompt
        assert "LOGISTICS" in prompt
        assert "WRAP_UP" in prompt or "WRAP-UP" in prompt or "Wrap-Up" in prompt or "wrap up" in prompt.lower()

    def test_includes_objection_counters(self):
        prompt = build_realtime_prompt("Alex", {"name": "Alex"})
        assert "Too expensive" in prompt
        assert "Not interested" in prompt
        assert "Too busy" in prompt

    def test_empty_profile_still_produces_valid_prompt(self):
        prompt = build_realtime_prompt("Unknown Student", {})
        assert "Unknown Student" in prompt
        assert "No profile information available" in prompt
        # Should still have all the structural sections
        assert "Conversation Flow" in prompt
        assert "Objection Counters" in prompt
        assert "Strategy Guidelines" in prompt

    def test_prompt_has_personality_instructions(self):
        prompt = build_realtime_prompt("Alex", {"name": "Alex"})
        assert "Confident but not pushy" in prompt
        assert "concise" in prompt.lower()

    def test_prompt_instructs_respect_for_hard_no(self):
        prompt = build_realtime_prompt("Alex", {"name": "Alex"})
        assert "hard no" in prompt.lower() or "firmly say no" in prompt.lower()
