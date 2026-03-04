from pydantic import BaseModel


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
    enrichment_status: str = "pending"
    enriched_profile: dict | None = None


class CallCreate(BaseModel):
    target_id: str
    mode: str = "text"  # text, browser, twilio


class CallResponse(BaseModel):
    call_id: str
    target_id: str
    target_name: str
    status: str
    mode: str
    created_at: str | None = None
    ended_at: str | None = None
    analysis_status: str | None = None


class TextInput(BaseModel):
    message: str
