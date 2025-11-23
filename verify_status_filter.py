import os
import django
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campus_event_manager.settings')
django.setup()

from events.models import Event, University, Venue, EventCategory

User = get_user_model()

def verify_status_filter():
    print("Verifying Status Filter...")
    
    # Setup data
    admin_user, _ = User.objects.get_or_create(username='admin_filter_test', email='admin_filter@test.com')
    admin_user.set_password('password')
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()
    
    uni1, _ = University.objects.get_or_create(name="Uni A", short_code="UA", domain="ua.edu")
    uni2, _ = University.objects.get_or_create(name="Uni B", short_code="UB", domain="ub.edu")
    
    venue, _ = Venue.objects.get_or_create(name="Test Venue", university=uni1, capacity=100)
    category, _ = EventCategory.objects.get_or_create(name="Test Category")
    
    # Create events
    Event.objects.create(
        title="Draft Event A", description="Desc", date_time=timezone.now() + timedelta(days=1),
        venue=venue, organizer=admin_user, host_university=uni1, category=category,
        participant_limit=10, status='draft'
    )
    Event.objects.create(
        title="Published Event A", description="Desc", date_time=timezone.now() + timedelta(days=2),
        venue=venue, organizer=admin_user, host_university=uni1, category=category,
        participant_limit=10, status='published'
    )
    Event.objects.create(
        title="Draft Event B", description="Desc", date_time=timezone.now() + timedelta(days=3),
        venue=venue, organizer=admin_user, host_university=uni2, category=category,
        participant_limit=10, status='draft'
    )
    
    client = APIClient()
    client.force_authenticate(user=admin_user)
    
    # Test 1: Filter by status 'draft'
    print("\nTest 1: Filter by status='draft'")
    response = client.get('/api/admin/events/', {'status': 'draft'})
    if response.status_code == 200:
        events = response.data
        print(f"Found {len(events)} draft events")
        for e in events:
            print(f"- {e['title']} ({e['status']})")
            if e['status'] != 'draft':
                print("FAIL: Found non-draft event")
    else:
        print(f"FAIL: {response.status_code}")
        
    # Test 2: Filter by status 'published'
    print("\nTest 2: Filter by status='published'")
    response = client.get('/api/admin/events/', {'status': 'published'})
    if response.status_code == 200:
        events = response.data
        print(f"Found {len(events)} published events")
        for e in events:
            print(f"- {e['title']} ({e['status']})")
    else:
        print(f"FAIL: {response.status_code}")

    # Test 3: Filter by university and status
    print(f"\nTest 3: Filter by university={uni1.id} and status='draft'")
    response = client.get('/api/admin/events/', {'university': uni1.id, 'status': 'draft'})
    if response.status_code == 200:
        events = response.data
        print(f"Found {len(events)} events")
        for e in events:
            print(f"- {e['title']} (Uni ID: {e['host_university']}, Status: {e['status']})")
            if e['host_university'] != uni1.id or e['status'] != 'draft':
                 print("FAIL: Incorrect filtering")
    else:
        print(f"FAIL: {response.status_code}")

if __name__ == '__main__':
    verify_status_filter()
