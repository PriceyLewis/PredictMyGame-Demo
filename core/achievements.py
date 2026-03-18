"""Achievement definitions and evaluation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Iterable, List, Optional

from django.db import transaction
from django.utils import timezone

from .models import (
    Module,
    PredictionSnapshot,
    StudyGoal,
    TimelineEvent,
    UserAchievement,
    UserProfile,
)


@dataclass(frozen=True)
class AchievementDefinition:
    code: str
    title: str
    description: str
    category: str
    metric: str
    threshold: float
    comparator: str = "gte"
    emoji: str = "🌟"


ACHIEVEMENT_DEFINITIONS: List[AchievementDefinition] = [
    AchievementDefinition(
        code="avg_50",
        title="Halfway Hero",
        description="Reach a 50% weighted average across your university modules.",
        category="Performance",
        metric="average",
        threshold=50,
        emoji="🚀",
    ),
    AchievementDefinition(
        code="avg_60",
        title="Upper Second Sprinter",
        description="Maintain a 60% weighted average (2:1 trajectory).",
        category="Performance",
        metric="average",
        threshold=60,
        emoji="🎯",
    ),
    AchievementDefinition(
        code="avg_70",
        title="First-Class Flyer",
        description="Stay at or above a 70% weighted average.",
        category="Performance",
        metric="average",
        threshold=70,
        emoji="👑",
    ),
    AchievementDefinition(
        code="modules_10",
        title="Module Maestro",
        description="Log 10 or more university modules in PredictMyGrade.",
        category="Consistency",
        metric="module_count",
        threshold=10,
        emoji="📚",
    ),
    AchievementDefinition(
        code="modules_20",
        title="Curriculum Captain",
        description="Keep track of 20+ modules — serious course coverage!",
        category="Consistency",
        metric="module_count",
        threshold=20,
        emoji="🧭",
    ),
    AchievementDefinition(
        code="goals_5",
        title="Goal Getter",
        description="Complete five study goals.",
        category="Habits",
        metric="completed_goals",
        threshold=5,
        emoji="✅",
    ),
    AchievementDefinition(
        code="streak_7",
        title="Snapshot Streak",
        description="Record a prediction snapshot every day for a full week.",
        category="Habits",
        metric="streak_days",
        threshold=7,
        emoji="🔥",
    ),
    AchievementDefinition(
        code="snapshots_25",
        title="Insight Collector",
        description="Capture 25 dashboard snapshots.",
        category="Habits",
        metric="snapshot_count",
        threshold=25,
        emoji="🗂️",
    ),
    AchievementDefinition(
        code="momentum_events",
        title="Timeline Trailblazer",
        description="Reach 15 timeline events (deadlines, goals, or AI highlights).",
        category="Momentum",
        metric="timeline_events",
        threshold=15,
        emoji="🗓️",
    ),
    AchievementDefinition(
        code="premium_plus",
        title="Premium Pioneer",
        description="Unlock Premium or an active free trial.",
        category="Membership",
        metric="has_premium",
        threshold=1,
        comparator="bool",
        emoji="💎",
    ),
]


def _weighted_average(modules: Iterable[Module]) -> float:
    total_score = 0.0
    total_credits = 0.0
    for module in modules:
        if module.grade_percent is None:
            continue
        credits = module.credits or 0
        total_credits += credits
        total_score += module.grade_percent * credits
    if not total_credits:
        return 0.0
    return total_score / total_credits


def _snapshot_streak(user) -> int:
    today = timezone.now().date()
    streak = 0
    for offset in range(0, 60):
        day = today - timedelta(days=offset)
        if not PredictionSnapshot.objects.filter(user=user, created_at__date=day).exists():
            break
        streak += 1
    return streak


def _collect_metrics(
    user,
    *,
    modules: Optional[List[Module]] = None,
    snapshots: Optional[List[PredictionSnapshot]] = None,
    current_avg: Optional[float] = None,
) -> Dict[str, float]:
    modules = modules or list(Module.objects.filter(user=user, level="UNI"))
    snapshots = snapshots or list(PredictionSnapshot.objects.filter(user=user))

    if current_avg is None:
        current_avg = _weighted_average(modules)

    completed_goals = StudyGoal.objects.filter(user=user, status="completed").count()
    timeline_events = TimelineEvent.objects.filter(user=user).count()

    return {
        "average": round(current_avg or 0.0, 2),
        "module_count": len(modules),
        "completed_goals": completed_goals,
        "streak_days": _snapshot_streak(user),
        "snapshot_count": len(snapshots),
        "timeline_events": timeline_events,
        "has_premium": 1 if getattr(user, "profile", None) and user.profile.has_premium_access else 0,
    }


def _meets_threshold(definition: AchievementDefinition, metrics: Dict[str, float]) -> bool:
    value = metrics.get(definition.metric, 0)
    if definition.comparator == "gte":
        return value >= definition.threshold
    if definition.comparator == "bool":
        return bool(value)
    if definition.comparator == "eq":
        return value == definition.threshold
    return False


@transaction.atomic
def evaluate_achievements(
    user,
    *,
    modules: Optional[List[Module]] = None,
    snapshots: Optional[List[PredictionSnapshot]] = None,
    current_avg: Optional[float] = None,
) -> List[UserAchievement]:
    """Ensure all applicable achievements are unlocked for the user."""

    metrics = _collect_metrics(user, modules=modules, snapshots=snapshots, current_avg=current_avg)
    unlocked: List[UserAchievement] = []

    for definition in ACHIEVEMENT_DEFINITIONS:
        if not _meets_threshold(definition, metrics):
            continue

        achievement, created = UserAchievement.objects.get_or_create(
            user=user,
            code=definition.code,
            defaults={
                "title": definition.title,
                "description": definition.description,
                "category": definition.category,
                "metadata": {
                    "metric": definition.metric,
                    "value": metrics.get(definition.metric),
                    "threshold": definition.threshold,
                    "emoji": definition.emoji,
                },
            },
        )
        if created:
            unlocked.append(achievement)
        else:
            updated_metadata = {
                "metric": definition.metric,
                "value": metrics.get(definition.metric),
                "threshold": definition.threshold,
                "emoji": definition.emoji,
            }
            if achievement.metadata != updated_metadata:
                achievement.metadata = updated_metadata
                achievement.save(update_fields=["metadata", "unlocked_at"])

    return unlocked


def achievement_status(
    user,
    achievements: Optional[Iterable[UserAchievement]] = None,
) -> List[Dict[str, object]]:
    """Return definitions annotated with unlocked state for display."""

    metrics = _collect_metrics(user)
    achievements = list(achievements) if achievements is not None else list(UserAchievement.objects.filter(user=user))
    unlocked_map = {achievement.code: achievement for achievement in achievements}
    items: List[Dict[str, object]] = []

    for definition in ACHIEVEMENT_DEFINITIONS:
        unlocked_obj = unlocked_map.get(definition.code)
        items.append(
            {
                "code": definition.code,
                "title": definition.title,
                "description": definition.description,
                "category": definition.category,
                "emoji": definition.emoji,
                "threshold": definition.threshold,
                "metric": definition.metric,
                "unlocked": unlocked_obj is not None,
                "meets_condition": _meets_threshold(definition, metrics),
                "value": metrics.get(definition.metric, 0),
                "share_token": unlocked_obj.share_token if unlocked_obj else None,
                "unlocked_at": unlocked_obj.unlocked_at if unlocked_obj else None,
            }
        )

    return items
