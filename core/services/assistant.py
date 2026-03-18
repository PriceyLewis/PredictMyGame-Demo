from __future__ import annotations

from typing import Iterable, List, Sequence

from django.utils import timezone

from ..constants import (
    AI_PERSONA_DEFAULT,
    AI_PERSONA_CHOICES,
    persona_options,
    get_persona,
)
from ..models import AIChatMessage


def available_personas() -> List[dict[str, str]]:
    return persona_options()


def normalise_persona(candidate: str | None) -> str:
    if not candidate:
        return AI_PERSONA_DEFAULT
    choices = dict(AI_PERSONA_CHOICES)
    return candidate if candidate in choices else AI_PERSONA_DEFAULT


def build_system_prompt(persona_id: str, stats: dict[str, object]) -> str:
    persona = get_persona(persona_id)
    lines = [
        f"You are PredictMyGrade's {persona['label']}.",
        persona["style"],
        "Keep replies under 140 words, use UK English, and focus on actionable, specific guidance.",
    ]

    average = stats.get("average")
    credits = stats.get("credits")
    target = stats.get("target_class")
    trend = stats.get("trend")
    if isinstance(average, (int, float)):
        lines.append(f"Current average: {average:.1f}%")
    if isinstance(credits, (int, float)):
        lines.append(f"Completed credits: {credits:.1f}")
    if target:
        lines.append(f"Target classification: {target}")
    if trend:
        lines.append(f"Recent trend: {trend}")

    top_module = stats.get("top_module")
    if top_module:
        lines.append(f"Strongest module: {top_module}")
    struggling_module = stats.get("struggling_module")
    if struggling_module:
        lines.append(f"Needs attention: {struggling_module}")

    upcoming = stats.get("upcoming_deadlines") or []
    if isinstance(upcoming, Iterable):
        deadlines_lines = []
        for item in list(upcoming)[:3]:
            title = item.get("title")
            due_in = item.get("due_in_days")
            if title and isinstance(due_in, int):
                suffix = "days" if due_in != 1 else "day"
                deadlines_lines.append(f"{title} in {due_in} {suffix}")
        if deadlines_lines:
            lines.append("Upcoming deadlines: " + "; ".join(deadlines_lines))

    return " ".join(lines)


def build_chat_messages(
    persona_id: str,
    question: str,
    history: Sequence[AIChatMessage],
    stats: dict[str, object],
) -> List[dict[str, str]]:
    prompt = build_system_prompt(persona_id, stats)
    messages: List[dict[str, str]] = [{"role": "system", "content": prompt}]
    for message in history:
        messages.append({"role": message.role, "content": message.content})
    messages.append({"role": "user", "content": question})
    return messages


def serialize_history(history: Sequence[AIChatMessage]) -> List[dict[str, object]]:
    items: List[dict[str, object]] = []
    for msg in history:
        items.append(
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": timezone.localtime(msg.created_at).isoformat(),
            }
        )
    return items
