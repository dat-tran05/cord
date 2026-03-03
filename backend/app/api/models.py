from enum import Enum

from pydantic import BaseModel


class EnrichmentStatus(str, Enum):
    PENDING = "pending"
    ENRICHING = "enriching"
    ENRICHED = "enriched"
    FAILED = "failed"


class EnrichedProfile(BaseModel):
    # Social / personality
    linkedin_summary: str = ""
    twitter_bio: str = ""
    public_posts: list[str] = []
    communication_style: str = ""

    # Academic / professional
    research_papers: list[str] = []
    lab_affiliations: list[str] = []
    projects: list[str] = []
    hackathons: list[str] = []

    # Lifestyle / interests
    blog_posts: list[str] = []
    reddit_activity: str = ""
    hobbies: list[str] = []
    communities: list[str] = []

    # AI-generated tactical fields
    talking_points: list[str] = []
    rapport_hooks: list[str] = []
    anticipated_objections: list[str] = []
    personalized_pitch_angles: list[str] = []

    # Raw research output
    raw_research_notes: str = ""


class TargetCreate(BaseModel):
    name: str
    school: str = ""
    major: str = ""
    year: str = ""
    interests: list[str] = []
    clubs: list[str] = []
    bio: str = ""


class TargetResponse(BaseModel):
    id: str
    name: str
    school: str
    major: str
    year: str
    interests: list[str]
    clubs: list[str]
    bio: str
    enrichment_status: EnrichmentStatus = EnrichmentStatus.PENDING
    enriched_profile: EnrichedProfile | None = None


class CallCreate(BaseModel):
    target_id: str
    mode: str = "text"  # text, browser, twilio


class CallResponse(BaseModel):
    call_id: str
    target_id: str
    target_name: str
    status: str
    mode: str


class TextInput(BaseModel):
    message: str
