import logging

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import MultipleObjectsReturned, ValidationError

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp

logger = logging.getLogger(__name__)


class DomainRestrictedAccountAdapter(DefaultAccountAdapter):
    """
    Restricts new sign-ups to certain email domains while still
    allowing normal login for existing users.
    """

    def is_open_for_signup(self, request):
        # Allow sign-ups via OAuth but validate domain in save_user()
        return True

    def clean_email(self, email):
        """Check that the user's email domain is allowed."""
        domain = email.split("@")[-1].lower()
        allowed_domains = getattr(
            settings,
            "ALLOWED_EMAIL_DOMAINS",
            ["edgehill.ac.uk", "student.edgehill.ac.uk", "gmail.com"],
        )
        if domain not in allowed_domains:
            raise ValidationError(
                f"Only accounts from {', '.join(allowed_domains)} may register."
            )
        return email


class ResilientSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Fallback adapter that gracefully handles duplicate SocialApp records.
    """

    def get_app(self, request, provider=None, client_id=None):
        try:
            return super().get_app(request, provider=provider, client_id=client_id)
        except MultipleObjectsReturned:
            provider_id = getattr(provider, "id", provider)
            site = get_current_site(request)
            qs = SocialApp.objects.filter(provider=provider_id, sites=site)
            if client_id:
                qs = qs.filter(client_id=client_id)
            app = qs.order_by("id").first()

            if not app:
                raise SocialApp.DoesNotExist(
                    f"Unable to find SocialApp for provider '{provider_id}' after resolving duplicates."
                )

            logger.warning(
                "Multiple SocialApp records detected for provider '%s' on site %s. "
                "Using the first match with id=%s.",
                provider_id,
                site.pk,
                app.pk,
            )
            return app

    def list_providers(self, request):
        providers = super().list_providers(request)
        unique = []
        seen = set()
        for provider in providers:
            provider_id = getattr(provider, "id", None)
            if not provider_id or provider_id in seen:
                continue
            unique.append(provider)
            seen.add(provider_id)
        return unique
