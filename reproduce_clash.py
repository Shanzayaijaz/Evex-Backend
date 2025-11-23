import os
import django
from datetime import datetime, timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_backend.settings')
django.setup()

from django.contrib.auth.models import User
from events.models import Event, Venue, University, EventCategory, Registration, UserProfile

def reproduce_clash():
    print("Setting up test data...")
    
    # Create a test user with unique username
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    username = f'clash_test_user_{unique_id}'
    email = f'clash_{unique_id}@test.com'
    
    user = User.objects.create_user(username=username, email=email, password='password')
    # Profile is created by signal
    
    # Create a university
    uni, _ = University.objects.get_or_create(name='Test Uni', short_code='TU', domain='test.edu')
    
    # Create a venue
    venue, _ = Venue.objects.get_or_create(name='Test Venue', university=uni, capacity=100)
    
    # Create a category
    cat, _ = EventCategory.objects.get_or_create(name='Test Category')
    
    # Create organizer
    organizer, _ = User.objects.get_or_create(username='organizer', email='org@test.com')
    
    # Create two overlapping events
    # Event 1: Today at 10:00 AM
    now = timezone.now()
    event1_time = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    event1, _ = Event.objects.get_or_create(
        title='Event 1',
        defaults={
            'description': 'Test Event 1',
            'date_time': event1_time,
            'venue': venue,
            'organizer': organizer,
            'host_university': uni,
            'category': cat,
            'participant_limit': 10,
            'status': 'published'
        }
    )
    
    # Event 2: Today at 11:00 AM (overlaps with Event 1 if duration is 2 hours)
    event2_time = event1_time + timedelta(hours=1)
    
    event2, _ = Event.objects.get_or_create(
        title='Event 2',
        defaults={
            'description': 'Test Event 2',
            'date_time': event2_time,
            'venue': venue,
            'organizer': organizer,
            'host_university': uni,
            'category': cat,
            'participant_limit': 10,
            'status': 'published'
        }
    )
    
    print(f"Event 1: {event1.title} at {event1.date_time}")
    print(f"Event 2: {event2.title} at {event2.date_time}")
    
    # Use APIClient to test the view logic
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    
    # Register for Event 1
    print("Registering for Event 1 via API...")
    response1 = client.post(f'/api/events/{event1.id}/register/')
    print(f"Event 1 Registration Status: {response1.status_code}")
    if response1.status_code != 201:
        print(f"Error: {response1.data}")
    
    # Attempt to register for Event 2 (should fail)
    print("Attempting to register for Event 2 via API (should clash)...")
    response2 = client.post(f'/api/events/{event2.id}/register/')
    print(f"Event 2 Registration Status: {response2.status_code}")
    
    if response2.status_code == 400 and 'clash' in str(response2.data).lower():
        print("PASS: User was prevented from registering for overlapping events.")
        print(f"Error message received: {response2.data}")
    else:
        print("FAIL: User was NOT prevented from registering.")
        print(f"Response: {response2.data}")

if __name__ == '__main__':
    reproduce_clash()
