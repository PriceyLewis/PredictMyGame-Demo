import json
from django.conf import settings

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Module


class WhatIfPredictViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="whatif",
            email="whatif@example.com",
            password="pass1234",
        )
        self.user.profile.set_premium(True)
        Module.objects.create(user=self.user, name="Current Module", credits=60, grade_percent=65)

    def _post(self, payload: dict):
        self.client.force_login(self.user)
        return self.client.post(
            reverse("core:predict_what_if"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_adjusted_points_reflect_study_hours(self):
        response = self._post(
            {
                "sims": [{"mark": 70, "credits": 20}],
                "target_avg": 72,
                "study_hours": 4,
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("adjusted_points", data)
        self.assertEqual(len(data["predicted_points"]), 1)
        self.assertEqual(len(data["adjusted_points"]), 1)
        self.assertGreater(data["adjusted_points"][0], data["predicted_points"][0])
        expected_gain = settings.WHAT_IF_HOUR_BOOST * 4
        self.assertAlmostEqual(data["hours_gain_per_week"], expected_gain, places=1)
        self.assertIn("Scenario 1", data["recommendations"][0])
        self.assertIn("scenario_summaries", data)
        self.assertEqual(len(data["scenario_summaries"]), 1)
        self.assertEqual(data["scenario_summaries"][0]["name"], "Scenario 1")
        self.assertIn("best_scenario", data)
        self.assertEqual(data["best_scenario"]["name"], "Scenario 1")
        self.assertIn("plan_summary", data)
        self.assertEqual(data["plan_summary"]["scenarios_tested"], 1)
        self.assertIsNotNone(data["plan_summary"]["headline"])

    def test_free_user_receives_upgrade_error(self):
        self.user.profile.set_premium(False)
        response = self._post(
            {
                "sims": [{"mark": 68, "credits": 20}],
            }
        )
        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertIn("error", payload)

    def test_missing_scenarios_returns_error(self):
        response = self._post({"sims": []})
        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertIn("error", payload)

    def test_named_scenario_reflected_in_response(self):
        response = self._post(
            {
                "sims": [{"name": "Aggressive Push", "mark": 75, "credits": 30}],
                "target_avg": 80,
                "study_hours": 6,
                "plan_weeks": 3,
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["scenario_summaries"][0]["name"], "Aggressive Push")
        self.assertIn("Aggressive Push", data["plan_summary"]["headline"])
        self.assertEqual(data["plan_weeks"], 3)

    def test_plan_timeline_generated_with_start_date(self):
        response = self._post(
            {
                "sims": [{"name": "Steady Path", "mark": 72, "credits": 30}],
                "target_avg": 78,
                "study_hours": 5,
                "study_start_date": "2025-01-06",
                "plan_weeks": 3,
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        plan = data["plan_summary"]
        timeline = plan["timeline"]
        self.assertEqual(len(timeline), 3)
        self.assertEqual([entry["week"] for entry in timeline], [1, 2, 3])
        self.assertTrue(timeline[0]["date"].startswith("2025-01"))
        self.assertEqual([entry["hours"] for entry in timeline], [5.0, 5.0, 5.0])
        self.assertTrue(all(entry["focus"] == "Current Module" for entry in timeline))
        targets = [entry["target"] for entry in timeline]
        self.assertTrue(all(targets[idx] <= targets[idx + 1] for idx in range(len(targets) - 1)))
        dates = [entry["date"] for entry in timeline]
        self.assertEqual(sorted(dates), dates)

    def test_simulation_page_includes_hour_gain(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:what_if_simulation"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("hour_gain", response.context)
        self.assertAlmostEqual(response.context["hour_gain"], settings.WHAT_IF_HOUR_BOOST)
        self.assertIn("module_limit", response.context)
        self.assertEqual(response.context["module_limit"], 20)
        self.assertIn("has_more_modules", response.context)
        self.assertFalse(response.context["has_more_modules"])
