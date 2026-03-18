from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.admin import UserProfileAdmin
from core.models import UserProfile


class AdminHubAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="regular", password="testpass")
        self.superuser = User.objects.create_superuser("admin", "admin@example.com", "testpass")

    def test_requires_superuser(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:admin_hub"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:dashboard"))

    def test_superuser_can_view_hub(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("core:admin_hub"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("total_users", response.context)
        self.assertIn("premium_users", response.context)


class AdminAnalyticsAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="regular", password="testpass")
        self.staff = User.objects.create_user(username="staff", password="testpass", is_staff=True)
        self.superuser = User.objects.create_superuser("admin", "admin@example.com", "testpass")

    def test_requires_superuser(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("core:admin_analytics"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:dashboard"))

    def test_superuser_can_view_dashboard(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("core:admin_analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("chart_labels", response.context)
        self.assertIn("chart_data", response.context)


class AdminUserManagementAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="student", password="pass123")
        self.staff = User.objects.create_user(username="manager", password="pass123", is_staff=True)

    def test_non_staff_redirected(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:admin_users"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:dashboard"))

    def test_staff_user_gets_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("core:admin_users"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("plan_breakdown", response.context)


class UserProfileAdminActionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser("root", "root@example.com", "pass123")
        self.student = User.objects.create_user("student", "student@example.com", "pass123")
        profile = self.student.profile
        profile.trial_cancelled = True
        profile.trial_started_at = None
        profile.trial_ends_at = None
        profile.plan_type = "free"
        profile.is_premium = False
        profile.save(
            update_fields=[
                "trial_cancelled",
                "trial_started_at",
                "trial_ends_at",
                "plan_type",
                "is_premium",
            ]
        )

        self.profile = profile
        self.factory = RequestFactory()
        self.admin = UserProfileAdmin(UserProfile, admin.site)

    def _action_request(self):
        request = self.factory.post("/")
        request.user = self.superuser
        # Attach session/messages so admin actions using message_user will pass.
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return request

    def test_mark_as_premium_action_sets_flag(self):
        queryset = UserProfile.objects.filter(pk=self.profile.pk)
        self.admin.mark_as_premium(self._action_request(), queryset)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_premium)
        self.assertEqual(self.profile.plan_type, "premium")

    def test_remove_premium_status_action_revokes_access(self):
        self.profile.set_premium(True)
        queryset = UserProfile.objects.filter(pk=self.profile.pk)
        self.admin.remove_premium_status(self._action_request(), queryset)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_premium)
        self.assertEqual(self.profile.plan_type, "free")
