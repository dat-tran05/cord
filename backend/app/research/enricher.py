import json
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

WEB_RESEARCH_PROMPT = """Research this person thoroughly for sales conversation preparation:

Name: {name}
School: {school}
Major: {major}
Year: {year}
Known interests: {interests}
Known clubs: {clubs}
Bio: {bio}

Search the web for any public information about this person. Look for:
1. LinkedIn profile or professional presence
2. Twitter/X bio or notable posts
3. Research papers or academic publications
4. Lab affiliations or research groups
5. Projects, hackathons, or competitions
6. Blog posts or personal websites
7. Reddit activity or online community involvement
8. Hobbies, communities, or extracurricular activities

Return ALL findings as a detailed research report. If you can't find information about this specific \
person, note what you searched for and provide relevant context about their school/major/interests \
that could be useful for building rapport."""

TACTICAL_ANALYSIS_PROMPT = """You are preparing a sales agent for a fun, casual phone call to sell a pen to an MIT student.

Based on the research below, produce a structured profile with two categories:

**Factual fields** (extracted from research — leave empty string or empty list if not found):
- linkedin_summary, twitter_bio, public_posts, communication_style
- research_papers, lab_affiliations, projects, hackathons
- blog_posts, reddit_activity, hobbies, communities

**Tactical fields** (AI-generated based on everything you know):
- talking_points: 5-7 specific conversation starters based on their real interests/background
- rapport_hooks: 3-5 things to mention that would make them feel understood
- anticipated_objections: 3-4 objections this specific person is likely to raise and why
- personalized_pitch_angles: 3-4 ways to pitch a pen that would resonate with THIS person

Person's seed data:
Name: {name} | School: {school} | Major: {major}

Research findings:
{research}

Return valid JSON matching the schema exactly."""

ENRICHED_PROFILE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "enriched_profile",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "linkedin_summary": {"type": "string"},
                "twitter_bio": {"type": "string"},
                "public_posts": {"type": "array", "items": {"type": "string"}},
                "communication_style": {"type": "string"},
                "research_papers": {"type": "array", "items": {"type": "string"}},
                "lab_affiliations": {"type": "array", "items": {"type": "string"}},
                "projects": {"type": "array", "items": {"type": "string"}},
                "hackathons": {"type": "array", "items": {"type": "string"}},
                "blog_posts": {"type": "array", "items": {"type": "string"}},
                "reddit_activity": {"type": "string"},
                "hobbies": {"type": "array", "items": {"type": "string"}},
                "communities": {"type": "array", "items": {"type": "string"}},
                "talking_points": {"type": "array", "items": {"type": "string"}},
                "rapport_hooks": {"type": "array", "items": {"type": "string"}},
                "anticipated_objections": {"type": "array", "items": {"type": "string"}},
                "personalized_pitch_angles": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "linkedin_summary",
                "twitter_bio",
                "public_posts",
                "communication_style",
                "research_papers",
                "lab_affiliations",
                "projects",
                "hackathons",
                "blog_posts",
                "reddit_activity",
                "hobbies",
                "communities",
                "talking_points",
                "rapport_hooks",
                "anticipated_objections",
                "personalized_pitch_angles",
            ],
            "additionalProperties": False,
        },
    },
}


class ProfileEnricher:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def enrich(self, target_data: dict) -> dict:
        """Run web research + tactical analysis. Returns dict matching EnrichedProfile schema."""
        raw_research = await self._web_research(target_data)
        enriched = await self._tactical_analysis(target_data, raw_research)
        enriched["raw_research_notes"] = raw_research
        return enriched

    async def _web_research(self, data: dict) -> str:
        """Use OpenAI Responses API with web_search_preview to research the target."""
        prompt = WEB_RESEARCH_PROMPT.format(
            name=data.get("name", ""),
            school=data.get("school", ""),
            major=data.get("major", ""),
            year=data.get("year", ""),
            interests=", ".join(data.get("interests", [])),
            clubs=", ".join(data.get("clubs", [])),
            bio=data.get("bio", ""),
        )

        response = await self._client.responses.create(
            model=settings.openai_supervisor_model,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )

        return response.output_text

    async def _tactical_analysis(self, data: dict, research: str) -> dict:
        """Parse research into structured profile with tactical fields."""
        prompt = TACTICAL_ANALYSIS_PROMPT.format(
            name=data.get("name", ""),
            school=data.get("school", ""),
            major=data.get("major", ""),
            research=research,
        )

        response = await self._client.chat.completions.create(
            model=settings.openai_supervisor_model,
            messages=[{"role": "user", "content": prompt}],
            response_format=ENRICHED_PROFILE_SCHEMA,
        )

        return json.loads(response.choices[0].message.content)
