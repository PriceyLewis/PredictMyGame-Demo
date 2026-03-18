from django.test import TestCase
from django.urls import reverse


class LegalPagesTests(TestCase):
    def test_privacy_policy_page_renders(self):
        response = self.client.get(reverse("core:privacy_policy"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacy Policy")

    def test_terms_page_renders(self):
        response = self.client.get(reverse("core:terms_of_service"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Terms of Service")

    def test_cookie_notice_page_renders(self):
        response = self.client.get(reverse("core:cookie_notice"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cookie Notice")

    def test_prediction_disclaimer_page_renders(self):
        response = self.client.get(reverse("core:prediction_disclaimer"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prediction Disclaimer")
