import pytest
from openai import AsyncOpenAI

from app.config import settings


SAMPLE_TARGET = {
    "name": "Alex Chen",
    "school": "MIT",
    "major": "Computer Science",
    "year": "Junior",
    "interests": ["robotics", "coffee", "mechanical keyboards"],
    "clubs": ["Robotics Club", "HackMIT"],
    "bio": "Building robots and drinking too much espresso.",
}

SAMPLE_TARGET_ENRICHED = {
    **SAMPLE_TARGET,
    "enriched_profile": {
        "linkedin_summary": "",
        "twitter_bio": "",
        "public_posts": [],
        "communication_style": "casual, tech-savvy",
        "research_papers": [],
        "lab_affiliations": ["MIT CSAIL Robotics"],
        "projects": ["Autonomous drone navigation"],
        "hackathons": ["HackMIT 2025 finalist"],
        "blog_posts": [],
        "reddit_activity": "",
        "hobbies": ["3D printing", "espresso brewing", "custom keyboards"],
        "communities": ["r/MechanicalKeyboards", "MIT Maker Space"],
        "talking_points": [
            "Ask about their drone project — what sensors are they using?",
            "HackMIT finalist — what did they build?",
            "Custom keyboards — do they prefer tactile or linear switches?",
            "Espresso setup — what machine do they use?",
            "CSAIL robotics — which lab are they in?",
        ],
        "rapport_hooks": [
            "Fellow keyboard enthusiast — bond over switch preferences",
            "Coffee nerd connection — compare brewing methods",
            "Maker culture — talk about 3D printing projects",
        ],
        "anticipated_objections": [
            "Too busy with robotics project to think about a pen",
            "Already has digital note-taking workflow (CS student)",
            "Budget-conscious — spending money on keyboards instead",
        ],
        "personalized_pitch_angles": [
            "Perfect for sketching robot designs and circuit diagrams",
            "The tactile feel rivals their favorite keyboard switches",
            "Every maker needs great tools — this pen is a precision instrument",
            "Sign their HackMIT winner certificate in style",
        ],
    },
}


@pytest.fixture
def sample_target():
    return SAMPLE_TARGET.copy()


@pytest.fixture
def sample_target_enriched():
    return SAMPLE_TARGET_ENRICHED.copy()


@pytest.fixture
def openai_client():
    return AsyncOpenAI(api_key=settings.openai_api_key)
