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
