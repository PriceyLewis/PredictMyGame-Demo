from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
class MockBillingFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="demo-user",
            email="demo@example.com",
            password="pass1234",
        )
        self.client.force_login(self.user)

    def test_mock_checkout_returns_local_success_url(self):
        response = self.client.post(
            reverse("core:create_checkout_session_default"),
            {"plan_type": "yearly"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["mock"])
        self.assertIn(reverse("core:payment_success"), payload["checkout_url"])
        self.assertIn("plan_type=yearly", payload["checkout_url"])

    def test_mock_payment_success_upgrades_user_without_real_payment(self):
        response = self.client.get(reverse("core:payment_success"), {"plan_type": "monthly"})
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.is_premium)
        self.assertTrue(self.user.profile.stripe_customer_id.startswith("mock_cus_"))

    def test_mock_cancel_subscription_downgrades_immediately(self):
        profile = self.user.profile
        profile.set_premium(True)
        profile.stripe_customer_id = "mock_cus_existing"
        profile.save(update_fields=["stripe_customer_id"])

        response = self.client.post(reverse("core:cancel_subscription"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "canceled")

        profile.refresh_from_db()
        self.assertFalse(profile.is_premium)
