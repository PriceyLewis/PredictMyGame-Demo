from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import DataExportLog, Module


class PrivacyDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("alice", "alice@example.com", "password123")
        Module.objects.create(user=self.user, name="Algorithms", level="UNI", credits=20, grade_percent=72)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("core:privacy_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_dashboard_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:privacy_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacy dashboard")

    def test_download_personal_data_logs_export(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:download_personal_data"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(DataExportLog.objects.filter(user=self.user, format="json").count(), 1)

    def test_legacy_csv_export_logs_entry(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:export_data"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DataExportLog.objects.filter(user=self.user, format="csv").exists())
