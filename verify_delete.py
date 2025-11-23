import os
import django
from django.conf import settings
from django.utils import timezone

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_backend.settings')
django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth.models import User
from events.models import UserProfile, University, Event, EventCategory, Venue
from events.views import AdminEventViewSet

def verify_delete():
    print("Starting hard delete verification...")

    # Setup
    uni, _ = University.objects.get_or_create(name="Delete Uni", defaults={'short_code': 'DU', 'domain': 'del.edu'})
    
    # Create Admin
    admin, _ = User.objects.get_or_create(username='admin_del', email='admin_d@test.com')
    if not admin.check_password('pass'): admin.set_password('pass'); admin.save()
    admin.is_staff = True
    admin.is_superuser = True
    admin.save()
    UserProfile.objects.get_or_create(user=admin, defaults={'user_type': 'organizer', 'university': uni})

    # Create Event to Delete
    venue, _ = Venue.objects.get_or_create(name="Delete Room", university=uni, defaults={'capacity': 10})
    category, _ = EventCategory.objects.get_or_create(name="General")
    
    event = Event.objects.create(
        title="Event to Delete",
        description="This event should be deleted",
        date_time=timezone.now() + timezone.timedelta(days=1),
        venue=venue,
        organizer=admin,
        host_university=uni,
        category=category,
        participant_limit=10,
        visibility='public',
        status='published'
    )
    
    print(f"Event created: {event.title} (ID: {event.id})")

    # Delete Event
    factory = APIRequestFactory()
    view = AdminEventViewSet.as_view({'delete': 'destroy'})
    
    print("\nDeleting event...")
    request = factory.delete(f'/api/admin/events/{event.id}/')
    force_authenticate(request, user=admin)
    response = view(request, pk=event.id)
    print(f"Delete Status: {response.status_code}")

    # Verify Deletion
    if Event.objects.filter(id=event.id).exists():
        print("FAILURE: Event still exists in database.")
        # Check status
        event.refresh_from_db()
        print(f"Event Status: {event.status}")
    else:
        print("SUCCESS: Event removed from database.")

if __name__ == "__main__":
    try:
        verify_delete()
    except Exception as e:
        print(f"Error: {e}")
