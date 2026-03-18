from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean
from typing import Iterable, List, Sequence

from django.contrib.auth import get_user_model
from django.utils import timezone

from ..models import (
    Module,
    PredictionSnapshot,
    SmartInsight,
    AIInsightSummary,
    UserProfile,
)
from ..utils import classify_percent
from .openai_client import get_openai_client, OpenAIConfigurationError

logger = logging.getLogger(__name__)
User = get_user_model()


def _run_insight_prompt(prompt: str) -> str | None:
    try:
        client = get_openai_client()
    except OpenAIConfigurationError as exc:  # pragma: no cover - env dependent
        logger.warning("OpenAI unavailable for insight generation: %s", exc)
        return None

    try:
        response = client.chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You generate academic performance insights. "
                        "Return concise actionable guidance."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_output_tokens=400,
        )
        return response.message
    except Exception:  # pragma: no cover - rely on logging
        logger.exception("AI insight completion failed")
        return None


@dataclass(slots=True)
class InsightPayload:
    title: str
    summary: str
    impact_score: float
    metadata: dict


def _user_modules(user) -> Sequence[Module]:
    return Module.objects.filter(user=user, level="UNI").order_by("-created_at")


def collect_performance_metrics(user) -> dict:
    modules = list(_user_modules(user))
    completed_modules = [m for m in modules if m.grade_percent is not None]
    avg = mean([m.grade_percent for m in completed_modules]) if completed_modules else 0.0
    credits_total = sum(m.credits or 0 for m in completed_modules)

    strongest = None
    weakest = None
    if completed_modules:
        strongest = max(completed_modules, key=lambda m: m.grade_percent or 0)
        weakest = min(completed_modules, key=lambda m: m.grade_percent or 0)

    snapshots = list(
        PredictionSnapshot.objects.filter(user=user)
        .order_by("-created_at")
        .values_list("average_percent", flat=True)[:8]
    )
    trend = None
    if len(snapshots) >= 2:
        trend_delta = (snapshots[0] or 0) - (snapshots[1] or 0)
        if trend_delta > 0.6:
            trend = "improving"
        elif trend_delta < -0.6:
            trend = "dropping"
        else:
            trend = "steady"

    return {
        "average": round(avg, 2),
        "credits": credits_total,
        "classification": classify_percent(avg),
        "strongest": strongest.name if strongest else None,
        "strongest_score": getattr(strongest, "grade_percent", None),
        "weakest": weakest.name if weakest else None,
        "weakest_score": getattr(weakest, "grade_percent", None),
        "trend": trend,
        "snapshot_history": list(reversed(snapshots)),
    }


def build_insight_prompt(user_profile: UserProfile, metrics: dict) -> str:
    user = user_profile.user
    persona = getattr(user_profile, "ai_persona", "mentor")
    strongest = metrics.get("strongest")
    weakest = metrics.get("weakest")

    lines = [
        "You are PredictMyGrade's analytics generator.",
        "Return 3 bullet insights for the student with actionable advice.",
        "Respond as JSON with keys: insights (array of {title, summary, impact_score (0-1), tag}).",
        "Keep summaries under 45 words and tailor guidance to UK higher education context.",
        f"Student username: {user.username}",
        f"Preferred persona: {persona}",
        f"Average mark: {metrics.get('average', 0):.1f}%",
        f"Classification: {metrics.get('classification', 'n/a')}",
        f"Completed credits: {metrics.get('credits', 0)}",
        f"Trend: {metrics.get('trend') or 'steady'}",
    ]
    if strongest:
        lines.append(f"Strongest module: {strongest} ({metrics.get('strongest_score', 0):.1f}%).")
    if weakest:
        lines.append(f"Needs support: {weakest} ({metrics.get('weakest_score', 0):.1f}%).")

    history = metrics.get("snapshot_history") or []
    if history:
        lines.append(f"Recent snapshot averages: {history[-5:]}")

    return "\n".join(lines)


def _parse_insight_response(raw: str | None) -> List[InsightPayload]:
    if not raw:
        return []
    import json

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("AI insight response was not valid JSON.")
        return []

    insights = parsed.get("insights") if isinstance(parsed, dict) else parsed
    payloads: List[InsightPayload] = []
    if not isinstance(insights, Iterable):
        return payloads
    for item in insights:
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        score = item.get("impact_score")
        tag = item.get("tag") or item.get("category")
        if not title or not summary:
            continue
        try:
            score_val = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            score_val = 0.5
        payloads.append(
            InsightPayload(
                title=title,
                summary=summary,
                impact_score=score_val,
                metadata={"tag": tag} if tag else {},
            )
        )
    return payloads


def heuristic_insights(metrics: dict) -> List[InsightPayload]:
    statements: List[InsightPayload] = []
    avg = metrics.get("average", 0.0)
    trend = metrics.get("trend") or "steady"
    strongest = metrics.get("strongest")
    weakest = metrics.get("weakest")

    if avg >= 70:
        statements.append(
            InsightPayload(
                title="High Distinction Trajectory",
                summary="Average performance is above 70%. Keep consolidating your strongest modules and start stretch goals.",
                impact_score=0.8,
                metadata={"tag": "achievement"},
            )
        )
    elif avg >= 60:
        statements.append(
            InsightPayload(
                title="2:1 Momentum",
                summary="Average marks are around the 2:1 boundary. Reinforce revision on heavier credit modules to stay ahead.",
                impact_score=0.7,
                metadata={"tag": "trend"},
            )
        )
    else:
        statements.append(
            InsightPayload(
                title="Opportunity to Recover",
                summary="Average performance is below 60%. Focus next week on lifting your lower scoring modules with targeted practice.",
                impact_score=0.6,
                metadata={"tag": "support"},
            )
        )

    if strongest:
        statements.append(
            InsightPayload(
                title="Leverage Your Strength",
                summary=f"{strongest} is your top module—capture what works there and apply it to upcoming assessments.",
                impact_score=0.65,
                metadata={"tag": "strength"},
            )
        )

    if weakest:
        statements.append(
            InsightPayload(
                title="Module to Reinforce",
                summary=f"{weakest} needs extra focus. Schedule a revision block and seek feedback on recent assignments.",
                impact_score=0.75,
                metadata={"tag": "focus"},
            )
        )

    if trend == "improving":
        statements.append(
            InsightPayload(
                title="Positive Trend",
                summary="Recent snapshots show improvement—capture this routine in your study tracker to keep momentum.",
                impact_score=0.7,
                metadata={"tag": "trend"},
            )
        )
    elif trend == "dropping":
        statements.append(
            InsightPayload(
                title="Trend Watch",
                summary="Recent performance dipped. Review time allocation and balance between modules with upcoming deadlines.",
                impact_score=0.8,
                metadata={"tag": "alert"},
            )
        )

    return statements[:3]


def generate_insights_for_user(profile: UserProfile) -> List[SmartInsight]:
    user = profile.user
    metrics = collect_performance_metrics(user)
    prompt = build_insight_prompt(profile, metrics)

    ai_message = _run_insight_prompt(prompt)
    payloads = _parse_insight_response(ai_message)
    if not payloads:
        payloads = heuristic_insights(metrics)

    today = timezone.now().date()
    SmartInsight.objects.filter(user=user, created_at__date=today).delete()

    created_insights: List[SmartInsight] = []
    for payload in payloads:
        insight = SmartInsight.objects.create(
            user=user,
            title=payload.title[:160],
            summary=payload.summary,
            impact_score=payload.impact_score,
            metadata=payload.metadata,
        )
        created_insights.append(insight)

    if created_insights:
        AIInsightSummary.objects.create(
            user=user,
            summary_text=" ".join(insight.summary for insight in created_insights),
            average_engagement=metrics.get("credits", 0),
            average_difficulty=metrics.get("strongest_score") or 0,
            average_variance=metrics.get("weakest_score") or 0,
            average_predicted=metrics.get("average", 0),
        )

    return created_insights


def capture_prediction_snapshot(profile: UserProfile) -> PredictionSnapshot | None:
    user = profile.user
    modules = list(_user_modules(user))
    completed = [m for m in modules if m.grade_percent is not None]
    if not completed:
        return None
    avg = mean([m.grade_percent for m in completed])

    today = timezone.now().date()
    existing = PredictionSnapshot.objects.filter(user=user, created_at__date=today).first()
    if existing:
        return existing

    classification = classify_percent(avg)
    snapshot = PredictionSnapshot.objects.create(
        user=user,
        average_percent=round(avg, 2),
        label="Auto Progress Snapshot",
        classification=classification,
    )
    return snapshot
