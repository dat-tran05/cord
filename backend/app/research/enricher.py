from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import settings


@dataclass
class TargetProfile:
    name: str
    school: str = ""
    major: str = ""
    year: str = ""
    interests: list[str] = field(default_factory=list)
    clubs: list[str] = field(default_factory=list)
    bio: str = ""
    enrichment_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "school": self.school,
            "major": self.major,
            "year": self.year,
            "interests": self.interests,
            "clubs": self.clubs,
            "bio": self.bio,
            "enrichment_notes": self.enrichment_notes,
        }


class ProfileEnricher:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def enrich(self, name: str, seed_data: dict | None = None) -> TargetProfile:
        profile = TargetProfile(name=name)

        if seed_data:
            profile.school = seed_data.get("school", profile.school)
            profile.major = seed_data.get("major", profile.major)
            profile.year = seed_data.get("year", profile.year)
            profile.interests = seed_data.get("interests", profile.interests)
            profile.clubs = seed_data.get("clubs", profile.clubs)
            profile.bio = seed_data.get("bio", profile.bio)

        # Auto-enrich using GPT to generate plausible talking points
        if profile.school or profile.major:
            profile.enrichment_notes = await self._generate_talking_points(profile)

        return profile

    async def _generate_talking_points(self, profile: TargetProfile) -> str:
        prompt = (
            f"Given this person's profile, generate 3-5 brief talking points I could use "
            f"to build rapport with them in a casual conversation. Be specific and creative.\n\n"
            f"Name: {profile.name}\n"
            f"School: {profile.school}\n"
            f"Major: {profile.major}\n"
            f"Interests: {', '.join(profile.interests)}\n"
            f"Clubs: {', '.join(profile.clubs)}\n"
        )
        response = await self._client.chat.completions.create(
            model=settings.openai_supervisor_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
