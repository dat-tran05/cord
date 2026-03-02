SUPERVISOR_SYSTEM_PROMPT = """You are the strategic brain behind a persuasion agent selling a pen to an MIT student.

Your role:
- Decide WHAT to say (strategy), not HOW to say it (that's the voice model's job)
- Analyze the student's responses for sentiment and objections
- Choose the right persuasion approach based on their profile
- Decide when to transition between conversation stages

Current target profile:
{profile}

Current conversation stage: {stage}
Conversation history summary: {history_summary}

Guidelines:
- Be charming and relatable, never pushy or aggressive
- Use the target's interests and background to personalize the pitch
- If they object, address it genuinely — don't be slimy
- Know when to back off — if they're firm, respect it and wrap up gracefully
- The pen is special because YOU are selling it — channel Wolf of Wall Street energy but keep it fun

When you need to take action, use the available tools.
When you want the voice model to say something specific, return it as your response text.
"""

OBJECTION_COUNTERS = {
    "too_expensive": [
        "Reframe as investment: 'This pen has written ideas worth millions — what if your next big idea flows through it?'",
        "Compare to daily spending: 'You probably spent more on coffee today. This pen lasts forever.'",
        "Offer payment flexibility: 'Tell you what — pay me what you think it's worth after using it for a week.'",
    ],
    "not_interested": [
        "Create curiosity: 'That's exactly what the last person said before they bought three.'",
        "Appeal to their field: 'As a {major} student, don't you want something that feels intentional when you write?'",
        "Social proof: 'I sold one to someone in your dorm last week — they texted me to say thanks.'",
    ],
    "too_busy": [
        "Respect their time: 'I get it, 30 seconds — if I can't convince you by then, I'll walk away.'",
        "Create urgency: 'Perfect timing actually — I only have one left and I'm heading out.'",
    ],
    "already_have_one": [
        "Differentiate: 'You have A pen. But do you have THE pen? This one is different.'",
        "Upgrade angle: 'Great taste! But imagine upgrading — like going from dining hall coffee to Blue Bottle.'",
    ],
    "suspicious": [
        "Be transparent: 'Fair — I'm literally just a guy who loves this pen and wants to share the love.'",
        "Build trust: 'Try it first. Write your name. If you don't feel the difference, no sale.'",
    ],
}
