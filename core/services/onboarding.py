from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from ..models import (
    Module,
    PlannedModule,
    UpcomingDeadline,
    UserProfile,
    WhatIfScenario,
)

SAMPLE_SEED_VERSION = 1


@dataclass(slots=True)
class OnboardingCTA:
    title: str
    body: str
    action_label: str
    action_url: str


@dataclass(slots=True)
class OnboardingSeedResult:
    seeded: bool
    cta: OnboardingCTA | None


def maybe_seed_onboarding_dataset(profile: UserProfile) -> OnboardingSeedResult:
    """
    Create a lightweight sample dataset the first time a user lands on the dashboard.
    A CTA is returned while the account only contains the generated data.
    """
    seeded = False
    if _should_seed(profile):
        _create_sample_records(profile)
        profile.sample_data_version = SAMPLE_SEED_VERSION
        profile.save(update_fields=["sample_data_version"])
        seeded = True

    cta = _cta_payload(profile) if _should_show_cta(profile) else None
    return OnboardingSeedResult(seeded=seeded, cta=cta)


def _should_seed(profile: UserProfile) -> bool:
    if not getattr(settings, "ONBOARDING_SAMPLE_DATA_ENABLED", True):
        return False
    if profile.sample_data_version >= SAMPLE_SEED_VERSION:
        return False
    user = profile.user
    has_existing_data = (
        Module.objects.filter(user=user).exists()
        or PlannedModule.objects.filter(user=user).exists()
        or UpcomingDeadline.objects.filter(user=user).exists()
        or WhatIfScenario.objects.filter(user=user).exists()
    )
    return not has_existing_data


def _should_show_cta(profile: UserProfile) -> bool:
    user = profile.user
    has_sample_modules = Module.objects.filter(user=user, is_sample=True).exists()
    has_real_modules = Module.objects.filter(user=user, is_sample=False).exists()
    return has_sample_modules and not has_real_modules


def _create_sample_records(profile: UserProfile) -> None:
    user = profile.user
    today = date.today()
    sample_modules = [
        ("Sample · Systems Strategy", 20, 68.5, 55.0),
        ("Sample · Adaptive Analytics", 20, 72.0, 62.0),
        ("Sample · Human Factors", 20, 64.0, 48.0),
        ("Sample · Research Studio", 40, 70.5, 35.0),
    ]

    with transaction.atomic():
        Module.objects.filter(user=user, is_sample=True).delete()
        PlannedModule.objects.filter(user=user, is_sample=True).delete()
        UpcomingDeadline.objects.filter(user=user, is_sample=True).delete()
        WhatIfScenario.objects.filter(user=user, is_sample=True).delete()

        Module.objects.bulk_create(
            [
                Module(
                    user=user,
                    level="UNI",
                    name=name,
                    credits=credits,
                    grade_percent=grade,
                    completion_percent=completion,
                    is_sample=True,
                )
                for name, credits, grade, completion in sample_modules
            ]
        )

        capstone = PlannedModule.objects.create(
            user=user,
            name="Sample · Capstone Sprint",
            credits=20,
            expected_grade=75.0,
            term="Semester 2",
            category="Core",
            status="In Progress",
            workload_hours=12,
            is_sample=True,
        )

        UpcomingDeadline.objects.create(
            user=user,
            module=capstone,
            title="Sample · Sprint Retrospective",
            due_date=today + timedelta(days=5),
            weight=0.25,
            notes="Auto-generated sample deadline.",
            is_sample=True,
        )

        WhatIfScenario.objects.create(
            user=user,
            avg_so_far=68.0,
            credits_done=120.0,
            difficulty_index=0.55,
            performance_variance=0.25,
            engagement_score=0.7,
            predicted_average=72.5,
            predicted_classification="Sample projection",
            is_sample=True,
        )


def _cta_payload(profile: UserProfile) -> OnboardingCTA:
    return OnboardingCTA(
        title="Connect your modules",
        body="Sample data is loaded so you can explore the dashboard. Replace entries tagged 'Sample' with your own modules or import your timetable.",
        action_label="Connect modules",
        action_url=reverse("core:modules_list"),
    )
