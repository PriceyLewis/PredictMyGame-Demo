# Update Summary (2025-02-11): Added freemium plan metadata, module completion tracking,
# timeline events, and goal-to-module sync utilities.

from datetime import timedelta
import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .constants import AI_PERSONA_CHOICES, AI_PERSONA_DEFAULT

from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------
class UserProfile(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("premium", "Premium"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    is_premium = models.BooleanField(default=False)
    has_seen_tour = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    trial_started_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    trial_cancelled = models.BooleanField(default=False)
    ai_persona = models.CharField(max_length=20, choices=AI_PERSONA_CHOICES, default=AI_PERSONA_DEFAULT)

    first_milestone_reached = models.BooleanField(default=False)
    milestone_effects_enabled = models.BooleanField(default=True)
    milestone_50_unlocked = models.BooleanField(default=False)
    milestone_60_unlocked = models.BooleanField(default=False)
    milestone_70_unlocked = models.BooleanField(default=False)

    plan_type = models.CharField(max_length=12, choices=PLAN_CHOICES, default="free")
    theme = models.CharField(
        max_length=10,
        choices=[("light", "Light"), ("dark", "Dark")],
        default="light",
    )
    stripe_customer_id = models.CharField(max_length=64, blank=True, null=True)
    premium_since = models.DateTimeField(null=True, blank=True)
    plan_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    sample_data_version = models.PositiveSmallIntegerField(default=0)
    has_seen_welcome = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.user.username}'s profile"

    def set_premium(self, value: bool) -> None:
        self.is_premium = bool(value)
        self.premium_since = timezone.now() if value else None
        self.plan_type = "premium" if value else "free"
        if value:
            self.cancel_at_period_end = False
        if not value:
            self.plan_period_end = None
            self.cancel_at_period_end = False
        if value:
            # Premium access supersedes the free trial window.
            self.trial_ends_at = None
            self.trial_started_at = None
            self.trial_cancelled = True
            update_fields = [
                "is_premium",
                "premium_since",
                "trial_started_at",
                "trial_ends_at",
                "trial_cancelled",
                "plan_type",
                "plan_period_end",
                "cancel_at_period_end",
            ]
        else:
            update_fields = ["is_premium", "premium_since", "plan_type", "plan_period_end", "cancel_at_period_end"]
        self.save(update_fields=update_fields)

    def start_free_trial(self, duration_days: int | None = None) -> None:
        """
        Trials are disabled: normalize any legacy trial state back to free access
        unless the user is already premium.
        """
        if self.is_premium:
            # Premium users stay untouched; clear stale trial flags.
            self.trial_started_at = None
            self.trial_ends_at = None
            self.trial_cancelled = True
            self.save(
                update_fields=[
                    "trial_started_at",
                    "trial_ends_at",
                    "trial_cancelled",
                ]
            )
            return

        self.trial_started_at = None
        self.trial_ends_at = None
        self.trial_cancelled = True
        if self.plan_type != "free":
            self.plan_type = "free"
            fields = ["trial_started_at", "trial_ends_at", "trial_cancelled", "plan_type"]
        else:
            fields = ["trial_started_at", "trial_ends_at", "trial_cancelled"]
        self.save(update_fields=fields)

    @property
    def is_trial_active(self) -> bool:
        return False

    @property
    def has_premium_access(self) -> bool:
        if self.is_premium:
            if self.plan_type != 'premium':
                self.plan_type = 'premium'
                self.save(update_fields=['plan_type'])
            return True
        if self.plan_type != 'free':
            self.plan_type = 'free'
            self.save(update_fields=['plan_type'])
        return False

    def set_persona(self, persona: str) -> None:
        if persona not in dict(AI_PERSONA_CHOICES):
            persona = AI_PERSONA_DEFAULT
        if self.ai_persona != persona:
            self.ai_persona = persona
            self.save(update_fields=["ai_persona"])


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        profile = UserProfile.objects.create(
            user=instance,
            trial_started_at=None,
            trial_ends_at=None,
            trial_cancelled=True,
            plan_type="free",
        )
    else:
        profile, _ = UserProfile.objects.get_or_create(user=instance)


@receiver(user_signed_up)
def create_profile_on_signup(request, user, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "trial_started_at": None,
            "trial_ends_at": None,
            "trial_cancelled": True,
            "plan_type": "free",
        },
    )
    if not profile.is_premium:
        profile.start_free_trial()


@receiver(social_account_added)
def create_profile_on_social(request, sociallogin, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(
        user=sociallogin.user,
        defaults={
            "trial_started_at": None,
            "trial_ends_at": None,
            "trial_cancelled": True,
            "plan_type": "free",
        },
    )
    if not profile.is_premium:
        profile.start_free_trial()


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------
class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="achievements")
    code = models.CharField(max_length=64)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=40, default="general")
    unlocked_at = models.DateTimeField(auto_now_add=True)
    share_token = models.CharField(max_length=36, unique=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("user", "code")
        ordering = ["-unlocked_at"]

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = secrets.token_urlsafe(18)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.code}"


class BillingEventLog(models.Model):
    EVENT_CHOICES = [
        ("upgrade", "Upgrade"),
        ("downgrade", "Downgrade"),
        ("cancel", "Cancel"),
        ("renewal", "Renewal"),
        ("failure", "Failure"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="billing_events")
    event = models.CharField(max_length=32, choices=EVENT_CHOICES)
    reason = models.CharField(max_length=255, default="", blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.event} @ {timezone.localtime(self.created_at).strftime('%Y-%m-%d %H:%M')}"


# ---------------------------------------------------------------------------
# Academic data
# ---------------------------------------------------------------------------
class Module(models.Model):
    LEVEL_CHOICES = [
        ("GCSE", "GCSE / Secondary"),
        ("ALEVEL", "A-Level"),
        ("BTEC", "BTEC"),
        ("UNI", "University"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="modules")
    level = models.CharField(max_length=12, choices=LEVEL_CHOICES, default="UNI")
    name = models.CharField(max_length=128)
    credits = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade_percent = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    completion_percent = models.FloatField(
        default=0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "name", "level"),)
        constraints = [
            models.CheckConstraint(check=models.Q(credits__gte=0), name="module_credits_nonnegative"),
            models.CheckConstraint(
                check=(
                    models.Q(grade_percent__isnull=True)
                    | (
                        models.Q(grade_percent__gte=0.0)
                        & models.Q(grade_percent__lte=100.0)
                    )
                ),
                name="module_grade_0_100_or_null",
            ),
            models.CheckConstraint(
                check=models.Q(completion_percent__gte=0.0)
                & models.Q(completion_percent__lte=100.0),
                name="module_completion_0_100",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.level})"


class PredictionSnapshot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="snapshots")
    average_percent = models.FloatField(null=True, blank=True)
    label = models.CharField(max_length=120, blank=True, null=True)
    classification = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        display = f"{self.average_percent:.1f}%" if self.average_percent is not None else "n/a"
        ts = timezone.localtime(self.created_at).strftime("%Y-%m-%d %H:%M")
        return f"{self.user.username} - {display} @ {ts}"


class WeeklyStat(models.Model):
    week_start = models.DateField(unique=True)
    users = models.IntegerField(default=0)
    snapshots = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.week_start} (users={self.users}, snaps={self.snapshots})"


class WhatIfScenario(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="whatif_scenarios")
    avg_so_far = models.FloatField()
    credits_done = models.FloatField()
    difficulty_index = models.FloatField()
    performance_variance = models.FloatField()
    engagement_score = models.FloatField()
    predicted_average = models.FloatField()
    predicted_classification = models.CharField(max_length=32)
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} – {self.predicted_average:.1f}% ({self.predicted_classification})"


class SimulationHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="simulations")
    created_at = models.DateTimeField(auto_now_add=True)
    predicted_average = models.FloatField()
    classification = models.CharField(max_length=50)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} – {self.predicted_average:.1f}% ({self.classification})"


class BugReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    steps = models.TextField(blank=True)
    screenshot = models.ImageField(upload_to="bug_reports/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("New", "New"),
            ("In Progress", "In Progress"),
            ("Resolved", "Resolved"),
            ("Ignored", "Ignored"),
        ],
        default="New",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bug Report"
        verbose_name_plural = "Bug Reports"

    def __str__(self) -> str:
        return f"Bug #{self.pk} – {self.user or 'Anonymous'}"


class Feedback(models.Model):
    CATEGORY_CHOICES = [
        ("General", "General"),
        ("Feature Suggestion", "Feature Suggestion"),
        ("Question / Help", "Question / Help"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="General")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User Feedback"
        verbose_name_plural = "User Feedback"

    def __str__(self) -> str:
        return f"{self.category} from {self.user or 'Anonymous'}"


# ---------------------------------------------------------------------------
# Account lifecycle tracking
# ---------------------------------------------------------------------------
class AccountDeletionLog(models.Model):
    user_id = models.IntegerField()
    username = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deleted_at"]
        verbose_name = "Account Deletion"
        verbose_name_plural = "Account Deletions"

    def __str__(self) -> str:
        when = timezone.localtime(self.deleted_at).strftime("%Y-%m-%d %H:%M")
        return f"{self.username or 'User'} (ID {self.user_id}) @ {when}"


class DataExportLog(models.Model):
    FORMAT_CHOICES = [
        ("json", "JSON"),
        ("csv", "CSV"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="data_export_logs")
    format = models.CharField(max_length=12, choices=FORMAT_CHOICES, default="json")
    record_count = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Data export"
        verbose_name_plural = "Data exports"

    def __str__(self) -> str:
        return f"{self.user.username} export ({self.format.upper()}) @ {timezone.localtime(self.created_at):%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# AI tracking and summaries
# ---------------------------------------------------------------------------
def normalized_score(percent: float, level: str) -> float:
    if percent is None:
        return 0.0
    level = (level or "").lower()
    if level == "gcse":
        return percent * 1.10
    if level == "college":
        return percent * 1.05
    return percent


class PredictionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    avg_so_far = models.FloatField()
    credits_done = models.FloatField()
    difficulty_index = models.FloatField()
    performance_variance = models.FloatField()
    engagement_score = models.FloatField()
    predicted_average = models.FloatField()
    predicted_classification = models.CharField(max_length=50)
    ai_insight = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} – {self.predicted_average:.1f}% ({self.predicted_classification})"


class AIInsightSummary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    summary_text = models.TextField()
    average_engagement = models.FloatField(default=0)
    average_difficulty = models.FloatField(default=0)
    average_variance = models.FloatField(default=0)
    average_predicted = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} – Summary ({self.created_at:%Y-%m-%d})"


class AIModelStatus(models.Model):
    last_retrained_at = models.DateTimeField(auto_now=True)
    free_accuracy = models.FloatField(default=0.0, help_text="R² score for free model")
    premium_accuracy = models.FloatField(default=0.0, help_text="R² score for premium model")

    class Meta:
        verbose_name = "AI Model Status"
        verbose_name_plural = "AI Model Status"

    def __str__(self) -> str:
        return (
            f"AI retrained {self.last_retrained_at:%Y-%m-%d %H:%M} "
            f"(Free={self.free_accuracy:.3f}, Premium={self.premium_accuracy:.3f})"
        )


class Snapshot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    average = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Snapshot {self.average:.1f}% @ {self.created_at.date()}"


class AIChatSession(models.Model):
    PERSONA_CHOICES = AI_PERSONA_CHOICES

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_chat_sessions",
    )
    persona = models.CharField(
        max_length=20,
        choices=PERSONA_CHOICES,
        default=AI_PERSONA_DEFAULT,
    )
    title = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user.username} assistant session ({self.persona})"

    @property
    def persona_label(self) -> str:
        return dict(self.PERSONA_CHOICES).get(self.persona, self.persona)


class AIChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    session = models.ForeignKey(
        AIChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.session.user.username} [{self.role}] {self.created_at:%Y-%m-%d %H:%M}"


class SmartInsight(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=160, blank=True)
    impact_score = models.FloatField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        label = self.title or "Insight"
        return f"{label} for {self.user.username} ({self.created_at.date()})"


class AIInsightFeedback(models.Model):
    RATING_CHOICES = (
        (1, "helpful"),
        (-1, "not_helpful"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="insight_feedback")
    insight = models.ForeignKey(SmartInsight, on_delete=models.CASCADE, related_name="feedback")
    rating = models.SmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "insight")
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        rating_label = dict(self.RATING_CHOICES).get(self.rating, "neutral")
        return f"{self.user.username} rated {self.insight_id} as {rating_label}"


class TimelineComparison(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    period_average = models.FloatField()
    overall_average = models.FloatField()
    change_percent = models.FloatField()
    change_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        sign = "+" if self.change_percent >= 0 else "-"
        return (
            f"{self.user.username}: {sign}{abs(self.change_percent):.1f}% "
            f"{self.change_type} ({self.start_date} -> {self.end_date})"
        )


# ---------------------------------------------------------------------------
# College & GCSE enhancements
# ---------------------------------------------------------------------------
class UcasOffer(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("applied", "Applied"),
        ("offer", "Offer received"),
        ("firm", "Firm choice"),
        ("insurance", "Insurance choice"),
    ]
    DECISION_CHOICES = [
        ("conditional", "Conditional"),
        ("unconditional", "Unconditional"),
        ("insurance", "Insurance (safety)"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ucas_offers")
    institution = models.CharField(max_length=150)
    course = models.CharField(max_length=150)
    required_points = models.PositiveIntegerField(default=0)
    target_points = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    decision_type = models.CharField(
        max_length=20, choices=DECISION_CHOICES, default="conditional"
    )
    deadline = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.institution} - {self.course} ({self.required_points} pts)"


class PersonalStatementProgress(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="personal_statement")
    word_count = models.PositiveIntegerField(default=0)
    target_word_count = models.PositiveIntegerField(default=4000)
    deadline = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} personal statement ({self.word_count}/{self.target_word_count})"


class SuperCurricularProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="super_curricular")
    key = models.CharField(max_length=50)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (("user", "key"),)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.key} ({'done' if self.completed else 'pending'})"


class RevisionSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="revision_sessions")
    subject = models.CharField(max_length=120)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date", "scheduled_time"]

    def __str__(self) -> str:
        time_display = self.scheduled_time.strftime("%H:%M") if self.scheduled_time else "Anytime"
        return f"{self.subject} @ {self.scheduled_date} {time_display}"


class PastPaperRecord(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("completed", "Completed"),
        ("review", "Needs review"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="past_papers")
    name = models.CharField(max_length=160)
    score_percent = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"


class ExamChecklistProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exam_checklist")
    key = models.CharField(max_length=50)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (("user", "key"),)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.key} ({'done' if self.completed else 'pending'})"


class GradeBoundary(models.Model):
    LEVEL_CHOICES = [
        ("GCSE", "GCSE"),
        ("ALEVEL", "A level"),
    ]

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="GCSE")
    subject = models.CharField(max_length=120)
    exam_board = models.CharField(max_length=80)
    grade = models.CharField(max_length=10)
    boundary_text = models.CharField(max_length=120)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subject", "grade"]
        unique_together = (("level", "subject", "exam_board", "grade"),)

    def __str__(self) -> str:
        return f"{self.level} {self.subject} {self.exam_board} grade {self.grade}"


# ---------------------------------------------------------------------------
# Future planning
# ---------------------------------------------------------------------------
class PlannedModule(models.Model):
    TERM_CHOICES = [
        ("Term 1", "Term 1"),
        ("Term 2", "Term 2"),
        ("Term 3", "Term 3"),
        ("Semester 1", "Semester 1"),
        ("Semester 2", "Semester 2"),
        ("Year-long", "Year-long"),
    ]

    CATEGORY_CHOICES = [
        ("Core", "Core"),
        ("Elective", "Elective"),
        ("Optional", "Optional"),
    ]

    STATUS_CHOICES = [
        ("Planned", "Planned"),
        ("Enrolled", "Enrolled"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="planned_modules")
    name = models.CharField(max_length=128, default="TBD")
    credits = models.PositiveIntegerField(default=20)
    expected_grade = models.FloatField(null=True, blank=True)
    term = models.CharField(max_length=20, choices=TERM_CHOICES, default="Term 1")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="Core")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Planned")
    workload_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        grade = f"{self.expected_grade:.1f}%" if self.expected_grade is not None else "n/a"
        return f"{self.user.username} - {self.name} ({self.credits}cr, {grade}, {self.term})"


class UpcomingDeadline(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="upcoming_deadlines")
    module = models.ForeignKey(
        PlannedModule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deadlines",
    )
    title = models.CharField(max_length=150)
    due_date = models.DateField()
    weight = models.FloatField(default=1.0)
    notes = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_sample = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_date"]

    def __str__(self) -> str:
        return f"{self.user.username} – {self.title} ({self.due_date})"


class StudyPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=100)
    date = models.DateField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.date})"


class StudyGoal(models.Model):
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "In Progress"),
        ("completed", "Completed"),
        ("paused", "Paused"),
    ]

    CATEGORY_CHOICES = [
        ("academic", "Academic"),
        ("assessment", "Assessment"),
        ("habit", "Habit"),
        ("application", "Application"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_goals")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="academic")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    due_date = models.DateField(null=True, blank=True)
    target_percent = models.FloatField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    module_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} goal: {self.title} ({self.status})"

    def mark_completed(self) -> None:
        from django.utils import timezone

        self.status = "completed"
        self.progress = 100
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "progress", "completed_at", "updated_at"])
        sync_module_progress_for_goal(self)


class TimelineEvent(models.Model):
    EVENT_CHOICES = [
        ("module_added", "Module Added"),
        ("module_removed", "Module Removed"),
        ("goal_completed", "Study Goal Completed"),
        ("snapshot_taken", "Snapshot Taken"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="timeline_events")
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"


def sync_module_progress_for_goal(goal: StudyGoal) -> Module | None:
    """
    Update a module's completion/grade metrics based on a goal's latest state.
    """
    module_name = (goal.module_name or "").strip()
    if not module_name:
        return None

    module = Module.objects.filter(user=goal.user, name__iexact=module_name).first()
    if not module:
        return None

    goals_for_module = StudyGoal.objects.filter(
        user=goal.user, module_name__iexact=module_name
    )
    total_goals = goals_for_module.count()
    completed_goals = goals_for_module.filter(status="completed").count()

    if total_goals:
        module_completion = round((completed_goals / total_goals) * 100, 1)
    else:
        module_completion = float(goal.progress or 0)

    update_fields: list[str] = []
    if module.completion_percent != module_completion:
        module.completion_percent = min(100.0, module_completion)
        update_fields.append("completion_percent")

    if goal.target_percent is not None:
        if module.grade_percent is None or goal.target_percent > module.grade_percent:
            module.grade_percent = goal.target_percent
            update_fields.append("grade_percent")

    if update_fields:
        update_fields.append("updated_at")
        module.save(update_fields=update_fields)
    return module


# ---------------------------------------------------------------------------
# Site updates
# ---------------------------------------------------------------------------
class WhatsNewEntry(models.Model):
    """
    Represents a short announcement shown on the What's New page.
    Admins can reorder items and toggle visibility without touching templates.
    """

    title = models.CharField(max_length=200)
    summary = models.CharField(max_length=280)
    body = models.TextField(blank=True)
    icon = models.CharField(
        max_length=16,
        blank=True,
        help_text="Optional emoji or short label shown before the entry title.",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Lower numbers appear first.",
    )
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "-published_at", "-created_at"]
        verbose_name = "What's new entry"
        verbose_name_plural = "What's new entries"

    def __str__(self) -> str:
        return self.title
