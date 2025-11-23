import os
import django
from django.conf import settings
from django.utils import timezone

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_backend.settings')
django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth.models import User
from events.models import UserProfile, University, Event, EventCategory, Venue, Registration, WaitlistEntry, RecentActivity
from events.views import EventViewSet

def reproduce_issue():
    print("Starting reproduction of Mehreen/Ali scenario...")

    # Setup
    uni, _ = University.objects.get_or_create(name="Test Uni", defaults={'short_code': 'TU', 'domain': 'test.edu'})
    organizer, _ = User.objects.get_or_create(username='organizer_rep', email='org_rep@test.com')
    UserProfile.objects.get_or_create(user=organizer, defaults={'user_type': 'organizer', 'university': uni})

    # Create Users
    try:
        mehreen = User.objects.get(username='Mehreen')
    except User.DoesNotExist:
        mehreen = User.objects.create_user(username='Mehreen', email='mehreen@test.com', password='pass')
    UserProfile.objects.get_or_create(user=mehreen, defaults={'user_type': 'student', 'university': uni})

    try:
        ali = User.objects.get(username='Ali')
    except User.DoesNotExist:
        ali = User.objects.create_user(username='Ali', email='ali@test.com', password='pass')
    UserProfile.objects.get_or_create(user=ali, defaults={'user_type': 'student', 'university': uni})

    # Cleanup
    Event.objects.filter(title="FIFA 25").delete()
    Venue.objects.filter(name="Gaming Room").delete()

    # Create Event "FIFA 25" with Capacity 1 (to force waitlist immediately)
    venue, _ = Venue.objects.get_or_create(name="Gaming Room", university=uni, defaults={'capacity': 1})
    category, _ = EventCategory.objects.get_or_create(name="Sports")
    
    event = Event.objects.create(
        title="FIFA 25",
        description="FIFA Tournament",
        date_time=timezone.now() + timezone.timedelta(days=1),
        venue=venue,
        organizer=organizer,
        host_university=uni,
        category=category,
        participant_limit=1, # Limit 1 for this test
        visibility='public',
        status='published'
    )

    factory = APIRequestFactory()
    register_view = EventViewSet.as_view({'post': 'register'})
    cancel_view = EventViewSet.as_view({'post': 'cancel_registration'})

    # 0. Ali registers and cancels (Pre-condition)
    print("\n0. Ali registers and cancels (Pre-condition)...")
    req = factory.post(f'/api/events/{event.id}/register/')
    force_authenticate(req, user=ali)
    register_view(req, pk=event.id)
    
    req = factory.post(f'/api/events/{event.id}/cancel_registration/')
    force_authenticate(req, user=ali)
    cancel_view(req, pk=event.id)
    print("Ali is now CANCELLED.")

    # 1. Mehreen Registers (Takes the spot)
    print("\n1. Mehreen registering...")
    req = factory.post(f'/api/events/{event.id}/register/')
    force_authenticate(req, user=mehreen)
    resp = register_view(req, pk=event.id)
    print(f"Mehreen Status: {resp.status_code}")

    # 2. Ali Joins Waitlist (Re-joining)
    print("\n2. Ali registering again (should be waitlisted)...")
    req = factory.post(f'/api/events/{event.id}/register/')
    force_authenticate(req, user=ali)
    resp = register_view(req, pk=event.id)
    print(f"Ali Status: {resp.status_code}, Data: {resp.data}")

    # 3. Mehreen Cancels
    print("\n3. Mehreen cancelling...")
    req = factory.post(f'/api/events/{event.id}/cancel_registration/')
    force_authenticate(req, user=mehreen)
    resp = cancel_view(req, pk=event.id)
    print(f"Mehreen Cancel Status: {resp.status_code}")

    # 4. Check Ali's Status
    print("\n4. Checking Ali's status...")
    reg = Registration.objects.filter(event=event, user=ali).first()
    if reg:
        print(f"Ali Registration Status: {reg.status}")
        if reg.status == 'registered':
            print("SUCCESS: Ali was promoted.")
        else:
            print("FAILURE: Ali was NOT promoted (Status is still {reg.status}).")
    else:
        print("FAILURE: Ali has NO registration record.")
        
    # Debug info
    print(f"Event Capacity: {event.participant_limit}")
    print(f"Active Registrations: {event.registration_set.filter(status__in=['registered', 'attended']).count()}")
    print(f"Waitlist Count: {WaitlistEntry.objects.filter(event=event).count()}")

if __name__ == "__main__":
    try:
        reproduce_issue()
    except Exception as e:
        print(f"Error: {e}")
