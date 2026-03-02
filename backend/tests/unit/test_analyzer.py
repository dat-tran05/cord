import pytest
from unittest.mock import AsyncMock, patch

from app.analytics.analyzer import CallAnalyzer


def test_analyzer_formats_transcript():
    analyzer = CallAnalyzer()
    transcript = [
        {"role": "agent", "content": "Hey Alex! Got a minute?"},
        {"role": "student", "content": "Uh, sure, who is this?"},
        {"role": "agent", "content": "I'm selling the best pen you'll ever own."},
    ]
    formatted = analyzer._format_transcript(transcript)
    assert "Agent:" in formatted
    assert "Student:" in formatted
    assert "best pen" in formatted
