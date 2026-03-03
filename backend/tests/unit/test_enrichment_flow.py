import pytest
from unittest.mock import AsyncMock, patch

from app import db
from app.services.handlers import handle_enrichment, handle_enrichment_failure


@pytest.fixture(autouse=True)
async def setup_db():
    await db.init_db(":memory:")
    yield
    await db.close_db()


@pytest.fixture
def sample_target():
    return {"name": "Alex Chen", "school": "MIT", "major": "CS"}


@pytest.fixture
def sample_enriched():
    return {
        "linkedin_summary": "CS at MIT",
        "twitter_bio": "",
        "public_posts": [],
        "communication_style": "",
        "research_papers": [],
        "lab_affiliations": [],
        "projects": [],
        "hackathons": [],
        "blog_posts": [],
        "reddit_activity": "",
        "hobbies": [],
        "communities": [],
        "talking_points": ["point1"],
        "rapport_hooks": [],
        "anticipated_objections": [],
        "personalized_pitch_angles": [],
        "raw_research_notes": "raw notes",
    }


async def test_enrichment_handler_sets_enriched(sample_target, sample_enriched):
    target_id = "test-001"
    await db.create_target(target_id, sample_target)

    with patch(
        "app.services.handlers.ProfileEnricher.enrich",
        new_callable=AsyncMock,
        return_value=sample_enriched,
    ):
        await handle_enrichment({"target_id": target_id, "target_data": sample_target})

    target = await db.get_target(target_id)
    assert target["enrichment_status"] == "enriched"
    assert target["enriched_profile"]["talking_points"] == ["point1"]


async def test_enrichment_handler_raises_on_error(sample_target):
    target_id = "test-002"
    await db.create_target(target_id, sample_target)

    with patch(
        "app.services.handlers.ProfileEnricher.enrich",
        side_effect=Exception("API error"),
    ):
        with pytest.raises(Exception, match="API error"):
            await handle_enrichment({"target_id": target_id, "target_data": sample_target})


async def test_failure_callback_sets_failed(sample_target):
    target_id = "test-003"
    await db.create_target(target_id, sample_target)

    await handle_enrichment_failure({"target_id": target_id, "target_data": sample_target}, "err")

    target = await db.get_target(target_id)
    assert target["enrichment_status"] == "failed"


async def test_enrichment_transitions_through_enriching(sample_target, sample_enriched):
    target_id = "test-004"
    await db.create_target(target_id, sample_target)

    target = await db.get_target(target_id)
    assert target["enrichment_status"] == "pending"

    statuses_seen = []
    original_update = db.update_enrichment

    async def tracking_update(tid, status, profile=None):
        statuses_seen.append(status)
        await original_update(tid, status, profile)

    with (
        patch(
            "app.services.handlers.ProfileEnricher.enrich",
            new_callable=AsyncMock,
            return_value=sample_enriched,
        ),
        patch("app.services.handlers.db.update_enrichment", side_effect=tracking_update),
    ):
        await handle_enrichment({"target_id": target_id, "target_data": sample_target})

    assert statuses_seen == ["enriching", "enriched"]
