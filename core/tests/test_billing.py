import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from core import views as core_views


@override_settings(STRIPE_WEBHOOK_SECRET="")
class StripeWebhookTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="stripe-user",
            email="stripe@example.com",
            password="pass1234",
        )
        self.profile = self.user.profile
        self.profile.trial_cancelled = True
        self.profile.trial_started_at = None
        self.profile.trial_ends_at = None
        self.profile.plan_type = "free"
        self.profile.is_premium = False
        self.profile.stripe_customer_id = "cus_initial"
        self.profile.save(
            update_fields=[
                "trial_cancelled",
                "trial_started_at",
                "trial_ends_at",
                "plan_type",
                "is_premium",
                "stripe_customer_id",
            ]
        )

    def _post_event(self, event_type, data_object):
        payload = json.dumps({"type": event_type, "data": {"object": data_object}})
        return self.client.post(
            reverse("core:stripe_webhook"),
            data=payload,
            content_type="application/json",
        )

    def test_checkout_completed_activates_premium(self):
        response = self._post_event(
            "checkout.session.completed",
            {
                "metadata": {"user_id": str(self.user.pk)},
                "customer": "cus_12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_premium)
        self.assertEqual(self.profile.stripe_customer_id, "cus_12345")

    def test_invoice_payment_failure_revokes_premium(self):
        self.profile.set_premium(True)
        self.profile.refresh_from_db()
        response = self._post_event(
            "invoice.payment_failed",
            {
                "customer": self.profile.stripe_customer_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_premium)
        self.assertEqual(self.profile.plan_type, "free")

    def test_subscription_update_reactivates_premium(self):
        self.profile.set_premium(False)
        response = self._post_event(
            "customer.subscription.updated",
            {"customer": self.profile.stripe_customer_id, "status": "active"},
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_premium)

    def test_subscription_update_past_due_revokes_premium(self):
        self.profile.set_premium(True)
        response = self._post_event(
            "customer.subscription.updated",
            {"customer": self.profile.stripe_customer_id, "status": "past_due"},
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_premium)
        self.assertEqual(self.profile.plan_type, "free")

    def test_subscription_cancel_at_period_end_drops_after_expiry(self):
        self.profile.set_premium(True)
        future_end = int((timezone.now() + timedelta(days=2)).timestamp())
        response = self._post_event(
            "customer.subscription.updated",
            {
                "customer": self.profile.stripe_customer_id,
                "status": "active",
                "cancel_at_period_end": True,
                "current_period_end": future_end,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_premium)

        past_end = int((timezone.now() - timedelta(days=1)).timestamp())
        response = self._post_event(
            "customer.subscription.updated",
            {
                "customer": self.profile.stripe_customer_id,
                "status": "active",
                "cancel_at_period_end": True,
                "current_period_end": past_end,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_premium)
        self.assertEqual(self.profile.plan_type, "free")

    def test_days_until_epoch_rounds_up(self):
        target = timezone.now() + timedelta(hours=26)
        days = core_views._days_until_epoch(int(target.timestamp()))
        self.assertEqual(days, 2)


@override_settings(BILLING_MOCK_MODE=True)
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
