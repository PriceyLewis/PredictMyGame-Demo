from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Create or update SocialApp entries from environment-backed settings."

    def handle(self, *args, **options):
        site = self._get_site()
        providers = {
            "google": "Google OAuth",
            "github": "GitHub OAuth",
            "microsoft": "Microsoft OAuth",
        }

        updated = 0
        skipped = []

        for provider, default_name in providers.items():
            app_settings = settings.SOCIALACCOUNT_PROVIDERS.get(provider, {}).get("APP", {})
            client_id = app_settings.get("client_id")
            secret = app_settings.get("secret")

            if not client_id or not secret:
                skipped.append(provider)
                continue

            social_app, created = SocialApp.objects.get_or_create(
                provider=provider,
                defaults={
                    "name": default_name,
                    "client_id": client_id,
                    "secret": secret,
                },
            )

            changed = False
            if social_app.client_id != client_id:
                social_app.client_id = client_id
                changed = True

            if social_app.secret != secret:
                social_app.secret = secret
                changed = True

            if not social_app.name:
                social_app.name = default_name
                changed = True

            if changed:
                social_app.save()

            if site not in social_app.sites.all():
                social_app.sites.add(site)
                changed = True

            if created or changed:
                updated += 1

        if updated:
            self.stdout.write(self.style.SUCCESS(f"Synced {updated} social app(s)."))

        if skipped:
            providers_list = ", ".join(sorted(skipped))
            self.stdout.write(
                self.style.WARNING(
                    "Skipped providers without credentials: " + providers_list
                )
            )

        if not updated and not skipped:
            self.stdout.write("No providers configured; nothing to sync.")

    def _get_site(self):
        site_id = getattr(settings, "SITE_ID", None)
        if site_id:
            return Site.objects.get(pk=site_id)

        return Site.objects.get_current()
