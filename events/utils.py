from typing import Optional

from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from .models import Notification, WaitlistEntry, Registration, UserProfile, Event
def send_email_notification(user, subject, message):
    """
    Send email notification to user
    """
    try:
        if user.email:
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@evex.com'),
                [user.email],
                fail_silently=False,
            )
            return True
    except Exception as e:
        print(f"Failed to send email: {e}")
    return False
def send_notification(user, title, message, notification_type, related_event=None):
    """Utility function to send notifications"""
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        related_event=related_event
    )
    
    # Also send email for important notifications
    if notification_type in ['registration_confirmation', 'waitlist_promotion', 'event_cancelled']:
        send_email_notification(user, title, message)
    
    return notification

def promote_from_waitlist(event):
    """Promote first user from waitlist when a spot opens"""
    try:
        with transaction.atomic():
            # Lock the event to ensure we have exclusive access to capacity
            # We need to reload the event to lock it
            event = Event.objects.select_for_update().get(pk=event.pk)
            
            if not event.is_full:
                # Lock the waitlist entry
                next_waitlist = WaitlistEntry.objects.filter(event=event).select_for_update().order_by('position').first()
                if next_waitlist:
                    # Register the user
                    registration, created = Registration.objects.get_or_create(
                        event=event,
                        user=next_waitlist.user,
                        defaults={'status': 'registered'}
                    )
                    
                    # Ensure status is registered (in case it was cancelled)
                    if not created and registration.status != 'registered':
                        registration.status = 'registered'
                        registration.save()
                    
                    # Remove from waitlist
                    next_waitlist.delete()
                    
                    # Update positions for remaining waitlist entries
                    remaining_entries = WaitlistEntry.objects.filter(event=event).order_by('position')
                    for idx, entry in enumerate(remaining_entries, 1):
                        entry.position = idx
                        entry.save()
                    
                    # Send notification to promoted user
                    user_name = next_waitlist.user.get_full_name() or next_waitlist.user.username
                    send_notification(
                        user=next_waitlist.user,
                        title="Waitlist Promotion",
                        message=f"{user_name} has been promoted from waitlist for {event.title}",
                        notification_type='waitlist_promotion',
                        related_event=event
                    )
                    
                    # Log Activity
                    from .models import RecentActivity
                    RecentActivity.objects.create(
                        user=next_waitlist.user,
                        event=event,
                        action='promoted'
                    )
                    
                    return True
    except Exception as e:
        print(f"Error promoting from waitlist: {e}")
        return False
    return False


def get_user_profile(user, create_if_missing: bool = False) -> Optional[UserProfile]:
    """
    Safely retrieve the profile for a user. Optionally create it if missing.
    """
    if not user:
        return None

    try:
        return user.profile
    except UserProfile.DoesNotExist:
        if create_if_missing:
            return UserProfile.objects.create(
                user=user,
                user_type='student',
                contact_number='',
                department='',
                student_id='',
            )
    except AttributeError:
        if create_if_missing:
            return UserProfile.objects.create(
                user=user,
                user_type='student',
                contact_number='',
                department='',
                student_id='',
            )
    return None