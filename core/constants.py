"""
Shared constants for AI personas and feature metadata.
"""

from __future__ import annotations

AI_PERSONAS = {
    "mentor": {
        "label": "Friendly Mentor",
        "description": "Supportive guide who keeps feedback motivating and practical.",
        "style": (
            "Warm, encouraging, highlights wins, suggests focused next steps, avoids jargon."
        ),
    },
    "coach": {
        "label": "Academic Coach",
        "description": "Goal-oriented strategist who breaks targets into manageable actions.",
        "style": (
            "Direct, structured, emphasises planning, goal alignment, and weekly habits."
        ),
    },
    "analyst": {
        "label": "Data Analyst",
        "description": "Evidence-driven persona that explains metrics and trends with precision.",
        "style": (
            "Analytical, references performance data, quantifies impact, keeps tone calm."
        ),
    },
}

AI_PERSONA_DEFAULT = "mentor"

AI_PERSONA_CHOICES = tuple((slug, meta["label"]) for slug, meta in AI_PERSONAS.items())


def get_persona(persona_id: str) -> dict[str, str]:
    return AI_PERSONAS.get(persona_id, AI_PERSONAS[AI_PERSONA_DEFAULT])


def persona_options() -> list[dict[str, str]]:
    return [
        {"id": slug, "label": meta["label"], "description": meta["description"]}
        for slug, meta in AI_PERSONAS.items()
    ]
