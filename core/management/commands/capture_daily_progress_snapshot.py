from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from core.models import UserProfile
from core.services.insights import capture_prediction_snapshot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Captures a daily prediction snapshot for every active user."

    def handle(self, *args, **options):
        profiles = UserProfile.objects.select_related("user").iterator()
        captured = 0

        for profile in profiles:
            try:
                snapshot = capture_prediction_snapshot(profile)
                if snapshot:
                    captured += 1
            except Exception:
                logger.exception("Failed capturing snapshot for user %s", profile.user_id)

        self.stdout.write(f"{captured} snapshots captured during this run.")
