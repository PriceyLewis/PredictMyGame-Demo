import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import AIInsightSummary, Module, SmartInsight, TimelineComparison


class AIReportsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("reporter", "report@example.com", "pass123")
        self.client.force_login(self.user)
        self.user.profile.set_premium(True)

        Module.objects.create(
            user=self.user,
            name="Neural Networks",
            level="UNI",
            credits=30,
            grade_percent=78,
        )

        self.old_summary = AIInsightSummary.objects.create(
            user=self.user,
            summary_text="Earlier summary body",
            average_engagement=0.65,
            average_difficulty=0.4,
            average_variance=0.1,
            average_predicted=75.2,
        )
        self.latest_summary = AIInsightSummary.objects.create(
            user=self.user,
            summary_text="Latest summary text",
            average_engagement=0.72,
            average_difficulty=0.35,
            average_variance=0.12,
            average_predicted=78.4,
        )

        self.insight = SmartInsight.objects.create(
            user=self.user,
            title="Stay focused",
            summary="Focus on dissertation milestones.",
            impact_score=0.9,
        )

        self.comparison = TimelineComparison.objects.create(
            user=self.user,
            start_date=date.today() - timedelta(days=14),
            end_date=date.today(),
            period_average=76.0,
            overall_average=74.5,
            change_percent=1.5,
            change_type="improving",
        )

    def test_ai_reports_renders_recent_records(self):
        response = self.client.get(reverse("core:ai_reports"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary_text"], self.latest_summary.summary_text)
        self.assertEqual(response.context["summaries"][0], self.latest_summary)
        self.assertEqual(response.context["insights"][0], self.insight)
        self.assertEqual(response.context["comparisons"][0], self.comparison)

    def test_export_ai_report_pdf_includes_contextual_data(self):
        self.user.first_name = "Report"
        self.user.last_name = "User"
        self.user.save(update_fields=["first_name", "last_name"])

        response = self.client.post(
            reverse("core:export_ai_report_pdf"),
            data=json.dumps({"request": "pdf"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("predictmygrade_ai_report.pdf", response["Content-Disposition"])

        pdf_text = response.content.decode("latin1")
        self.assertIn("Student: Report User", pdf_text)
        self.assertIn("Latest AI summary:", pdf_text)
        self.assertIn(self.insight.summary, pdf_text)
        self.assertIn("Trend comparisons:", pdf_text)
