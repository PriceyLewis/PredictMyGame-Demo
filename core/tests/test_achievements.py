from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.achievements import achievement_status, evaluate_achievements
from core.models import Module, PredictionSnapshot, UserAchievement


class AchievementEvaluationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("achiever", "achiever@example.com", "pass1234")

    def test_evaluate_unlocks_average_milestone(self):
        Module.objects.create(user=self.user, name="Algorithms", credits=20, grade_percent=72)
        Module.objects.create(user=self.user, name="Databases", credits=20, grade_percent=68)
        evaluate_achievements(self.user)

        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, code="avg_60").exists()
        )

    def test_status_reports_share_tokens(self):
        Module.objects.create(user=self.user, name="Machine Learning", credits=40, grade_percent=75)
        evaluate_achievements(self.user)
        status = achievement_status(self.user)
        unlocked = [item for item in status if item["unlocked"]]
        self.assertTrue(unlocked)
        self.assertIsNotNone(unlocked[0]["share_token"])


class AchievementViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("viewer", "viewer@example.com", "pass1234")
        Module.objects.create(user=self.user, name="Statistics", credits=30, grade_percent=72)
        PredictionSnapshot.objects.create(user=self.user, average_percent=72)
        evaluate_achievements(self.user)

    def test_achievements_center_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:milestone_history"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("achievements", response.context)

    def test_public_share_page(self):
        achievement = UserAchievement.objects.filter(user=self.user).first()
        url = reverse("core:achievement_share", args=[achievement.share_token])
        response = self.client.get(url)
        self.assertContains(response, achievement.title)
