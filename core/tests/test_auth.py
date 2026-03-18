from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from ..adapters import DomainRestrictedAccountAdapter


class DashboardAccessTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        login_required_url = reverse("account_login")
        self.assertTrue(response.url.startswith(login_required_url))
        self.assertIn("next=", response.url)


class PremiumGatingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@edgehill.ac.uk",
            password="pass1234",
        )
        self.profile = self.user.profile
        self.profile.trial_cancelled = True
        self.profile.trial_started_at = None
        self.profile.trial_ends_at = None
        self.profile.plan_type = "free"
        self.profile.is_premium = False
        self.profile.save(update_fields=[
            "trial_cancelled",
            "trial_started_at",
            "trial_ends_at",
            "plan_type",
            "is_premium",
        ])

    def test_ai_reports_redirects_non_premium_users(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:ai_reports"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:upgrade"))

    def test_ai_reports_allows_premium_users(self):
        self.profile.set_premium(True)
        self.profile.refresh_from_db()
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:ai_reports"))
        self.assertEqual(response.status_code, 200)


class DomainRestrictionTests(TestCase):
    def setUp(self):
        self.adapter = DomainRestrictedAccountAdapter()

    def test_allowed_domain_passes_validation(self):
        email = "student@edgehill.ac.uk"
        self.assertEqual(self.adapter.clean_email(email), email)

    def test_disallowed_domain_raises_error(self):
        with self.assertRaises(ValidationError):
            self.adapter.clean_email("user@example.com")
