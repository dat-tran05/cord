import json

from openai import AsyncOpenAI

from app.config import settings

ANALYSIS_PROMPT = """Analyze this sales call transcript where an agent tried to sell a pen to an MIT student.

Transcript:
{transcript}

Provide your analysis as JSON with these fields:
- effectiveness_score: 1-10 rating of overall persuasion effectiveness
- tactics_used: list of persuasion tactics identified (e.g., "rapport building", "social proof", "scarcity")
- tactics_that_worked: which tactics seemed to land well
- tactics_that_failed: which tactics fell flat or backfired
- objections_encountered: list of objections the student raised
- objection_handling_quality: 1-10 rating
- key_moments: list of {{timestamp_approx, description, impact}} for pivotal moments
- sentiment_arc: brief description of how the student's receptiveness changed over time
- improvement_suggestions: 3-5 specific, actionable suggestions for next time
- outcome: "sold", "rejected", "undecided"

Return ONLY valid JSON, no markdown formatting.
"""


class CallAnalyzer:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    def _format_transcript(self, transcript: list[dict]) -> str:
        lines = []
        for entry in transcript:
            role = entry["role"].capitalize()
            if role == "Agent":
                lines.append(f"Agent: {entry['content']}")
            else:
                lines.append(f"Student: {entry['content']}")
        return "\n".join(lines)

    async def analyze(self, transcript: list[dict]) -> dict:
        formatted = self._format_transcript(transcript)
        response = await self._client.chat.completions.create(
            model=settings.openai_supervisor_model,
            messages=[
                {"role": "user", "content": ANALYSIS_PROMPT.format(transcript=formatted)},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
