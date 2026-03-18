from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from core.models import DataExportLog, UserProfile
from core.utils import build_user_data_export

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Persists premium exports to the configured backup directory."

    def handle(self, *args, **options):
        now = timezone.now()
        backup_dir = Path(settings.PREMIUM_BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)

        formatted_time = now.strftime("%Y%m%dT%H%M%S")

        premium_profiles = list(
            UserProfile.objects.filter(is_premium=True).select_related("user")
        )

        def _backup_profile(profile: UserProfile, tag: str) -> bool:
            user = profile.user
            payload, record_count = build_user_data_export(user)
            if not payload:
                self.stdout.write(
                    f"Skipping backup for {user.get_username()} ({user.id}); no data generated."
                )
                return False
            safe_name = slugify(user.username or "") or f"user{user.id}"
            filename = f"backup-{tag}-{safe_name}-{user.id}-{formatted_time}.csv"
            path = backup_dir / filename
            try:
                path.write_text(payload, encoding="utf-8")
            except OSError:
                logger.exception("Failed to write backup for user %s", user.id)
                return False
            DataExportLog.objects.create(
                user=user,
                format="csv",
                record_count=record_count,
                notes=f"premium_backup ({tag})",
            )
            self.stdout.write(
                f"Stored backup for {user.get_username()} ({record_count} rows) at {path}"
            )
            return True

        premium_saved = sum(
            1 for profile in premium_profiles if _backup_profile(profile, "premium")
        )

        self.stdout.write(
            f"Premium backup finished: {premium_saved} premium exports."
        )
