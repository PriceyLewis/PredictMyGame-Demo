from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import UserProfile

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a user profile when a new user is created."""
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "is_premium": False,   # 👈 all new users start as free
                "milestone_effects_enabled": True,
                "theme": "light",
            }
        )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensure every user has a profile and save it safely."""
    if hasattr(instance, "userprofile"):
        instance.userprofile.save()
    else:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "is_premium": False,
                "milestone_effects_enabled": True,
                "theme": "light",
            }
        )
