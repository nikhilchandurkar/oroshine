import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from allauth.account.signals import user_signed_up

from .models import UserProfile, Appointment
from .metrics import active_users

logger = logging.getLogger(__name__)

User = get_user_model()


# ==========================================
# USER SIGNALS
# ==========================================

@receiver(post_save, sender=User)
def handle_user_post_save(sender, instance, created, raw=False, **kwargs):
    """
    Handles:
    - Active user metrics update
    - Profile creation (only on user creation)
    """

    if raw:
        return

    # Update active users metric
    count = User.objects.filter(is_active=True).count()
    active_users.set(count)

    # Create profile only on user creation
    if created:
        profile, profile_created = UserProfile.objects.get_or_create(user=instance)

        if profile_created:
            logger.info(f"Profile created for user {instance.id}")
            cache.set(f"user_profile:{instance.id}", profile, 1800)


# ==========================================
# ALLAUTH SOCIAL SIGNUP SIGNAL
# ==========================================

@receiver(user_signed_up)
def handle_user_signed_up(request, user, **kwargs):
    """
    Handle social signup (Google/Facebook avatar saving).
    """

    try:
        profile, _ = UserProfile.objects.get_or_create(user=user)

        sociallogin = kwargs.get("sociallogin")

        if sociallogin:
            provider = sociallogin.account.provider
            logger.info(f"Social signup: {user.username} via {provider}")

            picture_url = None

            if provider == "google":
                picture_url = sociallogin.account.extra_data.get("picture")

            elif provider == "facebook":
                picture_url = (
                    sociallogin.account.extra_data
                    .get("picture", {})
                    .get("data", {})
                    .get("url")
                )

            if picture_url:
                profile.social_avatar_url = picture_url
                profile.save(update_fields=["social_avatar_url"])
                request.session["social_avatar_url"] = picture_url

        # Cache profile
        cache.set(f"user_profile:{user.id}", profile, 1800)

        # Clear rate limits
        identifier = request.META.get("REMOTE_ADDR", "unknown")
        cache.delete(f"register:{identifier}")
        cache.delete(f"login:{identifier}")

    except Exception as e:
        logger.error(f"Error in user_signed_up: {e}", exc_info=True)


# ==========================================
# APPOINTMENT SIGNALS
# ==========================================

@receiver(post_save, sender=Appointment)
def invalidate_appointment_cache(sender, instance, **kwargs):
    """
    Invalidate appointment-related caches.
    """

    cache.delete(f"upcoming_appointments:{instance.user.id}")
    cache.delete(f"user_appointment_stats:{instance.user.id}")

    cache_key = (
        f"available_slots:{instance.date.strftime('%Y-%m-%d')}:{instance.doctor_id}"
    )
    cache.delete(cache_key)

    cache.delete("homepage_stats")


@receiver(post_delete, sender=Appointment)
def invalidate_appointment_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate caches when appointment is deleted.
    """

    cache.delete(f"upcoming_appointments:{instance.user.id}")
    cache.delete(f"user_appointment_stats:{instance.user.id}")

    cache_key = (
        f"available_slots:{instance.date.strftime('%Y-%m-%d')}:{instance.doctor_id}"
    )
    cache.delete(cache_key)


# ==========================================
# PROFILE SIGNALS
# ==========================================

@receiver(post_save, sender=UserProfile)
def invalidate_profile_cache(sender, instance, **kwargs):
    """
    Invalidate profile cache when profile changes.
    """
    cache.delete(f"user_profile:{instance.user.id}")
