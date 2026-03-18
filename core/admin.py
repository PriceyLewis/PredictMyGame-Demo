
# Update Summary (2025-02-11): Registered timeline events and surfaced plan metadata.
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from .models import AIModelStatus
from .models import (
    UserProfile,
    Module,
    PredictionSnapshot,
    WeeklyStat,
    WhatIfScenario,
    SimulationHistory,
    PredictionHistory,
    AIInsightSummary,
    BugReport,
    Feedback,
    AIChatSession,
    AIChatMessage,
    StudyGoal,
    TimelineEvent,
    DataExportLog,
    WhatsNewEntry,
    BillingEventLog,
)

# -------------------------------
# User Profiles
# -------------------------------
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "is_premium",
        "plan_type",
        "has_seen_tour",
        "joined_at",
        "premium_since",
    )
    list_filter = ("is_premium", "has_seen_tour", "theme")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("joined_at", "premium_since")
    ordering = ("-joined_at",)
    actions = ("mark_as_premium", "remove_premium_status")

    @admin.action(description="Grant premium access")
    def mark_as_premium(self, request, queryset):
        updated = 0
        for profile in queryset.select_related("user"):
            profile.set_premium(True)
            updated += 1
        if updated:
            self.message_user(
                request,
                f"Granted premium access to {updated} user{'s' if updated != 1 else ''}.",
                messages.SUCCESS,
            )

    @admin.action(description="Revoke premium access")
    def remove_premium_status(self, request, queryset):
        updated = 0
        for profile in queryset.select_related("user"):
            profile.set_premium(False)
            updated += 1
        if updated:
            self.message_user(
                request,
                f"Removed premium access from {updated} user{'s' if updated != 1 else ''}.",
                messages.WARNING,
            )


# -------------------------------
# Modules & Snapshots
# -------------------------------
@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "grade_percent", "credits", "user", "created_at")
    list_filter = ("level", "created_at")
    search_fields = ("name", "user__username")
    ordering = ("-created_at",)


@admin.register(PredictionSnapshot)
class PredictionSnapshotAdmin(admin.ModelAdmin):
    list_display = ("user", "average_percent", "label", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "label")
    ordering = ("-created_at",)


@admin.register(WeeklyStat)
class WeeklyStatAdmin(admin.ModelAdmin):
    list_display = ("week_start", "users", "snapshots")
    ordering = ("-week_start",)


# -------------------------------
# Simulations & Predictions
# -------------------------------
@admin.register(WhatIfScenario)
class WhatIfScenarioAdmin(admin.ModelAdmin):
    list_display = ("user", "predicted_classification", "predicted_average", "created_at")
    list_filter = ("predicted_classification",)
    search_fields = ("user__username",)
    ordering = ("-created_at",)


@admin.register(SimulationHistory)
class SimulationHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "predicted_average", "classification", "created_at")
    list_filter = ("classification",)
    search_fields = ("user__username", "notes")
    ordering = ("-created_at",)


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "predicted_average",
        "predicted_classification",
        "difficulty_index",
        "engagement_score",
        "created_at",
    )
    list_filter = ("predicted_classification", "created_at")
    search_fields = ("user__username", "ai_insight")
    ordering = ("-created_at",)


@admin.register(AIInsightSummary)
class AIInsightSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "average_predicted",
        "average_difficulty",
        "average_variance",
        "average_engagement",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("user__username", "summary_text")
    ordering = ("-created_at",)


@admin.register(AIChatSession)
class AIChatSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "persona", "is_active", "updated_at", "created_at")
    list_filter = ("persona", "is_active", "created_at")
    search_fields = ("user__username", "title")
    ordering = ("-updated_at",)


@admin.register(AIChatMessage)
class AIChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("session__user__username", "content")
    ordering = ("-created_at",)


@admin.register(StudyGoal)
class StudyGoalAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "category", "due_date", "progress", "updated_at")
    list_filter = ("status", "category", "due_date")
    search_fields = ("title", "user__username", "module_name")
    ordering = ("status", "due_date", "-updated_at")


@admin.register(TimelineEvent)
class TimelineEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event_type", "message", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("user__username", "message")
    ordering = ("-created_at",)


# -------------------------------
# Feedback & Bug Reports
# -------------------------------
@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("description", "steps", "user__username")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "category", "reviewed", "created_at")
    list_filter = ("category", "reviewed", "created_at")
    search_fields = ("message", "user__username")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(AIModelStatus)
class AIModelStatusAdmin(admin.ModelAdmin):
    list_display = ("last_retrained_at", "free_accuracy", "premium_accuracy")
    readonly_fields = ("last_retrained_at",)


@admin.register(DataExportLog)
class DataExportLogAdmin(admin.ModelAdmin):
    list_display = ("user", "format", "record_count", "created_at", "notes")
    list_filter = ("format", "created_at")
    search_fields = ("user__username", "notes")
    ordering = ("-created_at",)


@admin.register(WhatsNewEntry)
class WhatsNewEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "display_order", "published_at", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("title", "summary", "body")
    ordering = ("display_order", "-published_at", "-updated_at")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "summary", "body")}),
        ("Presentation", {"fields": ("icon", "display_order", "is_published", "published_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(BillingEventLog)
class BillingEventLogAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "reason", "created_at")
    list_filter = ("event", "created_at")
    search_fields = ("user__username", "user__email", "reason")


def clean_email(self, email):
    domain = email.split("@")[-1].lower()
    if domain not in self.ALLOWED_DOMAINS:
        # Redirect to a “domain not allowed” page instead of raising an error
        raise ValidationError(
            f"Sorry, sign-ups are limited to institutional emails ({', '.join(self.ALLOWED_DOMAINS)})."
        )
    return email
