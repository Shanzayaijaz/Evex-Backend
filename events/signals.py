from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


def _profile_defaults():
    return {
        'user_type': 'student',
        'contact_number': '',
        'department': '',
        'student_id': '',
    }


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    """
    Guarantee that every user has a related profile.
    """
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults=_profile_defaults()
        )
    else:
        try:
            instance.profile
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(
                user=instance,
                **_profile_defaults()
            )

