from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Module, PlannedModule, UpcomingDeadline, WhatIfScenario
from core.services.onboarding import SAMPLE_SEED_VERSION, maybe_seed_onboarding_dataset


class OnboardingSampleDataTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    @override_settings(ONBOARDING_SAMPLE_DATA_ENABLED=True)
    def test_seed_creates_sample_records(self):
        user = self.User.objects.create_user("seed-user", password="pass123")
        profile = user.profile

        result = maybe_seed_onboarding_dataset(profile)

        self.assertTrue(result.seeded)
        self.assertIsNotNone(result.cta)
        self.assertEqual(Module.objects.filter(user=user, is_sample=True).count(), 4)
        self.assertEqual(PlannedModule.objects.filter(user=user, is_sample=True).count(), 1)
        self.assertEqual(UpcomingDeadline.objects.filter(user=user, is_sample=True).count(), 1)
        self.assertEqual(WhatIfScenario.objects.filter(user=user, is_sample=True).count(), 1)
        profile.refresh_from_db()
        self.assertEqual(profile.sample_data_version, SAMPLE_SEED_VERSION)

    @override_settings(ONBOARDING_SAMPLE_DATA_ENABLED=True)
    def test_existing_data_blocks_seeding(self):
        user = self.User.objects.create_user("existing-user", password="pass123")
        Module.objects.create(
            user=user,
            name="Real Module",
            level="UNI",
            credits=20,
            grade_percent=65.0,
        )
        profile = user.profile

        result = maybe_seed_onboarding_dataset(profile)

        self.assertFalse(result.seeded)
        self.assertIsNone(result.cta)
        self.assertEqual(Module.objects.filter(user=user, is_sample=True).count(), 0)

    @override_settings(ONBOARDING_SAMPLE_DATA_ENABLED=False)
    def test_flag_prevents_seeding(self):
        user = self.User.objects.create_user("flag-user", password="pass123")
        profile = user.profile

        result = maybe_seed_onboarding_dataset(profile)

        self.assertFalse(result.seeded)
        self.assertIsNone(result.cta)
        self.assertEqual(Module.objects.filter(user=user).count(), 0)
