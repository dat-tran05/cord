import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.research.enricher import ProfileEnricher


@pytest.fixture
def enricher():
    with patch("app.research.enricher.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_supervisor_model = "gpt-4o-mini"
        e = ProfileEnricher()
        yield e


@pytest.fixture
def sample_target():
    return {
        "name": "Alex Chen",
        "school": "MIT",
        "major": "Computer Science",
        "year": "2026",
        "interests": ["robotics", "coffee"],
        "clubs": ["HackMIT"],
        "bio": "",
    }


@pytest.fixture
def sample_enriched():
    return {
        "linkedin_summary": "CS student at MIT",
        "twitter_bio": "",
        "public_posts": [],
        "communication_style": "casual and technical",
        "research_papers": [],
        "lab_affiliations": [],
        "projects": ["RoboCup team"],
        "hackathons": ["HackMIT 2025"],
        "blog_posts": [],
        "reddit_activity": "",
        "hobbies": ["coffee brewing"],
        "communities": [],
        "talking_points": ["Ask about RoboCup"],
        "rapport_hooks": ["Coffee enthusiasm"],
        "anticipated_objections": ["Too busy with research"],
        "personalized_pitch_angles": ["The engineer's pen"],
    }


async def test_enrich_runs_both_phases(enricher, sample_target, sample_enriched):
    enricher._web_research = AsyncMock(return_value="Found LinkedIn profile...")
    enricher._tactical_analysis = AsyncMock(return_value=sample_enriched)

    result = await enricher.enrich(sample_target)

    enricher._web_research.assert_called_once_with(sample_target)
    enricher._tactical_analysis.assert_called_once_with(sample_target, "Found LinkedIn profile...")
    assert result["talking_points"] == ["Ask about RoboCup"]
    assert result["raw_research_notes"] == "Found LinkedIn profile..."


async def test_web_research_uses_responses_api(enricher, sample_target):
    mock_response = MagicMock()
    mock_response.output_text = "Research findings here"
    enricher._client.responses = MagicMock()
    enricher._client.responses.create = AsyncMock(return_value=mock_response)

    result = await enricher._web_research(sample_target)

    call_kwargs = enricher._client.responses.create.call_args.kwargs
    assert call_kwargs["tools"] == [{"type": "web_search_preview"}]
    assert "Alex Chen" in call_kwargs["input"]
    assert result == "Research findings here"


async def test_tactical_analysis_uses_structured_output(enricher, sample_target, sample_enriched):
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(sample_enriched)
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    enricher._client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await enricher._tactical_analysis(sample_target, "some research")

    call_kwargs = enricher._client.chat.completions.create.call_args.kwargs
    assert "response_format" in call_kwargs
    assert result["talking_points"] == ["Ask about RoboCup"]
    assert result["personalized_pitch_angles"] == ["The engineer's pen"]
