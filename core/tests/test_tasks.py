from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from core import tasks
from core.models import UserProfile


class CeleryTaskTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.premium_user = User.objects.create_user("premium-task", "p@example.com", "pass123")
        self.premium_user.profile.set_premium(True)

        self.mock_free_user = User.objects.create_user("mock-free-task", "t@example.com", "pass123")

        self.free_user = User.objects.create_user("free-task", "f@example.com", "pass123")
        free_profile = self.free_user.profile
        free_profile.trial_cancelled = True
        free_profile.trial_started_at = None
        free_profile.trial_ends_at = None
        free_profile.plan_type = "free"
        free_profile.save(
            update_fields=[
                "trial_cancelled",
                "trial_started_at",
                "trial_ends_at",
                "plan_type",
            ]
        )

    @mock.patch("core.tasks._call_management_command")
    def test_weekly_retrain_models_runs_management_command(self, mock_command):
        tasks.weekly_retrain_models()
        mock_command.assert_called_once_with("retrain_ai")

    @mock.patch("core.tasks._call_management_command")
    def test_dispatch_weekly_reports_runs_management_command(self, mock_command):
        tasks.dispatch_weekly_reports()
        mock_command.assert_called_once_with("send_weekly_report")

    @mock.patch("core.tasks.generate_insights_for_user", return_value=["insight"])
    def test_generate_weekly_ai_insights_targets_only_premium_users(
        self, mock_generate_insights
    ):
        tasks.generate_weekly_ai_insights()
        called_profiles = [call.args[0] for call in mock_generate_insights.call_args_list]
        user_ids = {profile.user_id for profile in called_profiles}
        self.assertIn(self.premium_user.id, user_ids)
        self.assertNotIn(self.mock_free_user.id, user_ids)
        self.assertNotIn(self.free_user.id, user_ids)

    @mock.patch("core.tasks.capture_prediction_snapshot")
    def test_capture_daily_progress_snapshot_handles_failures(self, mock_capture):
        profiles = list(UserProfile.objects.select_related("user").all())

        def side_effect(profile):
            if profile.user == self.premium_user:
                return object()
            if profile.user == self.mock_free_user:
                raise RuntimeError("boom")
            return None

        mock_capture.side_effect = side_effect

        tasks.capture_daily_progress_snapshot()

        self.assertEqual(mock_capture.call_count, len(profiles))
        observed_profiles = [call.args[0] for call in mock_capture.call_args_list]
        self.assertCountEqual(profiles, observed_profiles)
