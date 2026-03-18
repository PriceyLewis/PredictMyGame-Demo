"""
Utility helpers for the PredictMyGrade dashboard.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from django.db.models import Avg
from django.utils import timezone

from .ml import predict_average
from .models import (
    Module,
    PlannedModule,
    PredictionSnapshot,
    SmartInsight,
    StudyGoal,
    TimelineComparison,
    TimelineEvent,
    UpcomingDeadline,
    UserProfile,
)


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------
def classify_percent(avg: Optional[float]) -> str:
    if avg is None:
        return "Unknown"
    if avg >= 70:
        return "First"
    if avg >= 60:
        return "Upper Second (2:1)"
    if avg >= 50:
        return "Lower Second (2:2)"
    if avg >= 40:
        return "Third"
    return "Fail"


def next_threshold(avg: float) -> Tuple[float, str]:
    if avg < 40:
        return 40.0, "Pass Mark"
    if avg < 50:
        return 50.0, "Third Class"
    if avg < 60:
        return 60.0, "Lower Second (2:2)"
    if avg < 70:
        return 70.0, "Upper Second (2:1)"
    if avg < 100:
        return 100.0, "First Class"
    return avg, "Outstanding"


def resolve_premium_status(user, profile=None) -> dict:
    """
    Return a consistent view of a user's premium state for templates and views.
    Staff get full access for QA and support, even without a paid plan.
    """
    profile = profile or getattr(user, "profile", None) or getattr(user, "userprofile", None)
    has_access = False
    plan_type = "free"
    plan_label = "Free"
    plan_days_remaining: int | None = None
    plan_cancel_at_end = False
    trial_active = False

    if profile:
        has_access = profile.has_premium_access
        plan_type = profile.plan_type or "free"
        plan_cancel_at_end = bool(getattr(profile, "cancel_at_period_end", False))
        trial_active = False

        if profile.plan_period_end:
            try:
                remaining_days = (
                    (
                        timezone.localtime(profile.plan_period_end)
                        - timezone.localtime(timezone.now())
                    ).total_seconds()
                    / 86400
                )
                if remaining_days >= 0:
                    plan_days_remaining = math.ceil(remaining_days)
            except Exception:
                plan_days_remaining = None

        if has_access:
            plan_label = "Premium"

    if getattr(user, "is_staff", False) and not has_access:
        has_access = True
        if plan_type == "free":
            plan_type = "premium"
        if plan_label == "Free":
            plan_label = "Premium"

    return {
        "profile": profile,
        "has_access": has_access,
        "plan_type": plan_type or "free",
        "plan_label": plan_label,
        "plan_days_remaining": plan_days_remaining,
        "plan_cancel_at_end": plan_cancel_at_end,
        "is_trial_active": trial_active,
    }


LETTER_POINTS = {
    "A*": 56,
    "A": 48,
    "B": 40,
    "C": 32,
    "D": 24,
    "E": 16,
    "U": 0,
    "9": 9,
    "8": 8,
    "7": 7,
    "6": 6,
    "5": 5,
    "4": 4,
    "3": 3,
    "2": 2,
    "1": 1,
}


def letter_to_points(letter: str) -> Optional[float]:
    if not letter:
        return None
    normalised = str(letter).strip().upper()
    return float(LETTER_POINTS.get(normalised)) if normalised in LETTER_POINTS else None


def to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def smart_tip(avg: Optional[float]) -> str:
    if avg is None:
        return "Add modules to unlock personalised insights."
    if avg < 40:
        return "Focus on the highest weight assessments to reach a pass."
    if avg < 50:
        return "Target steady improvements in weaker modules."
    if avg < 60:
        return "A push on key modules can lift you into 2:1 territory."
    if avg < 70:
        return "Consistent distinction-level work will secure a First."
    return "Excellent performance – keep reinforcing strong habits."


def calculate_ucas_points(value) -> int:
    if isinstance(value, str):
        return int(LETTER_POINTS.get(value.strip().upper(), 0))
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return 0
    if pct >= 80:
        return 56
    if pct >= 70:
        return 48
    if pct >= 60:
        return 40
    if pct >= 50:
        return 32
    if pct >= 40:
        return 24
    if pct >= 30:
        return 16
    return 0


# ---------------------------------------------------------------------------
# AI prediction helpers
# ---------------------------------------------------------------------------


@dataclass
class PredictionResult:
    average: float
    confidence: float
    model_label: Optional[str] = None
    personal_weight: float = 0.0


def personalised_prediction(
    user,
    avg_so_far: float,
    credits_done: float,
    difficulty: float,
    variance: float,
    engagement: float,
) -> PredictionResult:
    profile = UserProfile.objects.filter(user=user).first()
    is_premium = bool(profile and getattr(profile, "is_premium", False))
    extras = {
        "difficulty_index": difficulty,
        "performance_variance": variance,
        "engagement_score": engagement,
    }
    confidence = 55.0
    model_label = None
    try:
        global_pred, confidence, meta, _ = predict_average(
            user,
            avg_so_far=avg_so_far,
            credits_done=credits_done,
            premium=is_premium,
            extra=extras,
        )
        model_label = meta.get("model_label") if isinstance(meta, dict) else None
    except Exception:
        global_pred = avg_so_far
        confidence = 55.0
        model_label = None

    modules = Module.objects.filter(user=user, level="UNI", grade_percent__isnull=False)
    personal_weight = 0.0
    blended = global_pred
    if modules.exists():
        user_avg = modules.aggregate(Avg("grade_percent"))["grade_percent__avg"] or 0
        module_count = modules.count()
        personal_weight = min(0.4, 0.05 * module_count)
        blended = (1 - personal_weight) * global_pred + personal_weight * user_avg

    average = round(max(0.0, min(100.0, blended)), 2)
    confidence = round(max(0.0, min(100.0, confidence or 0.0)), 1)
    personal_weight_percent = round(personal_weight * 100, 1)

    return PredictionResult(
        average=average,
        confidence=confidence,
        model_label=model_label,
        personal_weight=personal_weight_percent,
    )


def generate_timeline_comparison(user) -> Optional[float]:
    snapshots = PredictionSnapshot.objects.filter(user=user).order_by("-created_at")[:2]
    if len(snapshots) < 2:
        return None

    latest, previous = snapshots[0], snapshots[1]
    prev_avg = previous.average_percent or 0.0
    new_avg = latest.average_percent or 0.0
    change = round(new_avg - prev_avg, 2)
    change_type = "improvement" if change >= 0 else "drop"

    TimelineComparison.objects.create(
        user=user,
        start_date=previous.created_at.date(),
        end_date=latest.created_at.date(),
        period_average=new_avg,
        overall_average=prev_avg,
        change_percent=change,
        change_type=change_type,
    )
    return change


def generate_smart_insight_from_comparisons(user) -> Optional[str]:
    comparisons = TimelineComparison.objects.filter(user=user).order_by("-created_at")[:5]
    if not comparisons:
        return None

    latest = comparisons[0]
    change = latest.change_percent
    direction = "improved" if change >= 0 else "dropped"

    summary_lines = [
        (
            f"Between {latest.start_date:%b %d} and {latest.end_date:%b %d} your performance "
            f"{direction} by {abs(change):.1f}% "
            f"(period {latest.period_average:.1f}% vs overall {latest.overall_average:.1f}%)."
        )
    ]

    if len(comparisons) >= 3:
        trend_changes = [comp.change_percent for comp in reversed(comparisons)]
        avg_change = sum(trend_changes) / len(trend_changes)
        trend_direction = "upward" if avg_change > 0 else "downward"
        summary_lines.append(
            f"Recent trend shows a {trend_direction} trajectory averaging {avg_change:+.1f}% per comparison."
        )
        if avg_change > 3:
            summary_lines.append("Momentum is excellent – keep leaning into what works.")
        elif avg_change > 0:
            summary_lines.append("Steady progress – stay consistent to keep the curve rising.")
        elif avg_change > -3:
            summary_lines.append("Minor dip – review recent challenges and rebalance.")
        else:
            summary_lines.append("Noticeable decline – revisit your plan and tackle blockers early.")
    else:
        if change > 5:
            summary_lines.append("Great jump this period – your effort is paying off.")
        elif change > 0:
            summary_lines.append("Solid improvement – keep reinforcing good habits.")
        elif change > -5:
            summary_lines.append("Slight dip – a small tweak could restore momentum.")
        else:
            summary_lines.append("Large drop – reassess tough modules and plan recovery steps.")

    summary = " ".join(summary_lines)
    SmartInsight.objects.create(user=user, summary=summary)
    return summary


# ---------------------------------------------------------------------------
# Target planner helpers
# ---------------------------------------------------------------------------
TARGET_THRESHOLDS = {
    "First": 70.0,
    "Upper Second (2:1)": 60.0,
    "Lower Second (2:2)": 50.0,
    "Third": 40.0,
}


@dataclass
class TargetPlan:
    target_class: str
    target_avg: float
    remaining_credits: float
    required_avg_remaining: float
    ai_feedback: str
    module_breakdown: List[Dict[str, float]]


def calculate_future_target(
    current_avg: float,
    completed_credits: float,
    target_class: str = "First",
    total_credits: float = 120,
    is_premium: bool = False,
) -> Dict[str, object]:
    if total_credits <= 0:
        return {"error": "Total credits must be greater than zero."}
    if completed_credits < 0:
        return {"error": "Completed credits cannot be negative."}
    if completed_credits > total_credits:
        return {"error": "Completed credits cannot exceed total credits."}

    target_avg = TARGET_THRESHOLDS.get(target_class, 70.0)
    remaining = max(0.0, total_credits - completed_credits)

    if remaining == 0:
        return {
            "target_class": target_class,
            "target_avg": target_avg,
            "remaining_credits": 0.0,
            "required_avg_remaining": 0.0,
            "ai_feedback": "All credits complete – your current average defines the classification.",
            "module_breakdown": [],
        }

    required_total = target_avg * total_credits
    achieved_total = current_avg * completed_credits
    required_avg_remaining = (required_total - achieved_total) / remaining

    tone = "exceeded"
    feedback = "Excellent work – you are already ahead of the target."
    if required_avg_remaining > 100:
        tone = "impossible"
        feedback = "Even perfect scores will not reach this classification. Consider a new target."
    elif required_avg_remaining >= 75:
        tone = "ambitious"
        feedback = "Very ambitious – focus on the heaviest-weight modules to make this viable."
    elif required_avg_remaining >= 65:
        tone = "challenging"
        feedback = "Challenging but achievable with strong grades in remaining modules."
    elif required_avg_remaining >= 55:
        tone = "steady"
        feedback = "Maintain solid work to stay on track."
    elif required_avg_remaining >= 40:
        tone = "safe"
        feedback = "You are comfortably on pace – concentrate on consistency."

    if is_premium:
        premium_notes = {
            "ambitious": "Prioritise 20 credit modules where +8% gains have the most impact.",
            "challenging": "Schedule high-focus study blocks around tougher modules.",
            "steady": "Keep reinforcing your lower grades to build a buffer.",
            "safe": "Consider stretch goals to push above the target.",
        }
        feedback += f" {premium_notes.get(tone, '')}".strip()

    module_size = 20
    remaining_modules = max(1, int(round(remaining / module_size)))
    breakdown: List[Dict[str, object]] = []
    for index in range(remaining_modules):
        offset = index - (remaining_modules - 1) / 2
        suggested = required_avg_remaining + offset * 0.6
        if suggested >= 75:
            difficulty = "Very Hard"
        elif suggested >= 65:
            difficulty = "Manageable"
        elif suggested >= 55:
            difficulty = "Comfortable"
        else:
            difficulty = "Easy"
        breakdown.append(
            {
                "module": f"Future Module {index + 1}",
                "suggested_grade": round(max(0.0, min(100.0, suggested)), 2),
                "difficulty": difficulty,
            }
        )

    return {
        "target_class": target_class,
        "target_avg": round(target_avg, 2),
        "remaining_credits": round(remaining, 2),
        "required_avg_remaining": round(required_avg_remaining, 2),
        "ai_feedback": feedback,
        "module_breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# Mentor messaging
# ---------------------------------------------------------------------------
def generate_ai_mentor_message(avg: float, trend: str, tone: str) -> str:
    tone = tone or "motivational"
    trend = trend or "steady"

    if tone == "analytical":
        if trend == "improving":
            return "Performance is trending upward. Capture what changed and double down."
        if trend == "dropping":
            return "Performance slipped – review tough modules and shift revision time."
        return "Performance is stable. Track key metrics weekly to stay proactive."

    if tone == "celebratory":
        if trend == "improving":
            return "Outstanding progress! Celebrate the win and keep the streak alive."
        if trend == "dropping":
            return "Small dip, but you are still in great shape. Regroup and stay confident."
        return "Consistency unlocked – you are mastering this level."

    # motivational (default)
    if trend == "improving":
        return "Great momentum – each study block is paying off."
    if trend == "dropping":
        return "A short setback is a setup for a comeback. Focus on one module at a time."
    return "Steady work builds strong results. Keep nudging the average upward."


def generate_ai_study_tip(user, avg: float, trend: Optional[str] = None) -> str:
    trend_tip = {
        "improving": "Progress is climbing – keep the pace while it feels natural.",
        "dropping": "Trend is dipping – lean into high-credit modules this week.",
    }.get(trend, "Consistency rules growth – keep sessions focused and realistic.")

    future_modules = PlannedModule.objects.filter(user=user)
    module_note = ""
    if future_modules.exists():
        total_credits = sum(m.credits or 0 for m in future_modules)
        expected = [
            m.expected_grade for m in future_modules if m.expected_grade is not None
        ]
        expected_avg = sum(expected) / len(expected) if expected else None
        module_note = f" You have {future_modules.count()} planned modules covering {total_credits} credits."
        if expected_avg:
            module_note += f" Planned average target is {expected_avg:.1f}%."

    deadlines = UpcomingDeadline.objects.filter(
        user=user, completed=False, due_date__gte=date.today()
    )
    deadline_note = ""
    if deadlines.exists():
        nearest = deadlines.order_by("due_date").first()
        days_left = (nearest.due_date - date.today()).days
        deadline_note = (
            f" Next deadline \"{nearest.title}\" is in {days_left} day"
            f"{'s' if days_left != 1 else ''}."
        )
    else:
        deadline_note = " No deadlines on the horizon – a good time to get ahead."

    return f"{trend_tip}{module_note}{deadline_note}".strip()


def build_user_data_export(user):
    """
    Construct the CSV payload used for manual exports and automated backups.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    columns = [
        "section",
        "title",
        "category",
        "credits",
        "grade",
        "completion",
        "timestamp",
        "notes",
    ]
    writer.writerow(columns)

    modules = Module.objects.filter(user=user).order_by("name")
    for module in modules:
        grade_value = f"{module.grade_percent:.2f}" if module.grade_percent is not None else ""
        completion_value = f"{module.completion_percent:.1f}"
        writer.writerow(
            [
                "module",
                module.name,
                module.level,
                module.credits,
                grade_value,
                completion_value,
                timezone.localtime(module.created_at).isoformat() if module.created_at else "",
                "",
            ]
        )

    goals = StudyGoal.objects.filter(user=user).order_by("status", "due_date")
    for goal in goals:
        target_value = f"{goal.target_percent:.1f}" if goal.target_percent is not None else ""
        progress_value = f"{goal.progress}"
        goal_timestamp = goal.completed_at or goal.updated_at or goal.created_at
        writer.writerow(
            [
                "goal",
                goal.title,
                goal.category,
                "",
                target_value,
                progress_value,
                timezone.localtime(goal_timestamp).isoformat() if goal_timestamp else "",
                goal.module_name or goal.description[:120],
            ]
        )

    events = TimelineEvent.objects.filter(user=user).order_by("-created_at")[:100]
    for event in events:
        writer.writerow(
            [
                "timeline",
                event.message[:120],
                event.event_type,
                "",
                "",
                "",
                timezone.localtime(event.created_at).isoformat() if event.created_at else "",
                "",
            ]
        )

    payload = buffer.getvalue()
    total_rows = modules.count() + goals.count() + events.count()
    return payload, total_rows

