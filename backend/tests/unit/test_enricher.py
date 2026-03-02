import pytest
from unittest.mock import AsyncMock, patch

from app.research.enricher import ProfileEnricher, TargetProfile


def test_target_profile_from_seed():
    profile = TargetProfile(name="Alex Chen", school="MIT")
    assert profile.name == "Alex Chen"
    assert profile.school == "MIT"
    assert profile.interests == []


def test_target_profile_to_dict():
    profile = TargetProfile(
        name="Alex Chen",
        school="MIT",
        major="Computer Science",
        interests=["robotics", "coffee"],
    )
    d = profile.to_dict()
    assert d["name"] == "Alex Chen"
    assert d["major"] == "Computer Science"


async def test_enrich_with_user_provided_data():
    enricher = ProfileEnricher()
    enricher._generate_talking_points = AsyncMock(return_value="Talking points here")
    profile = await enricher.enrich(
        name="Alex Chen",
        seed_data={"school": "MIT", "major": "CS", "interests": ["robotics"]},
    )
    assert profile.name == "Alex Chen"
    assert profile.major == "CS"
    assert "robotics" in profile.interests
