import os
import django
import threading
import time
from django.db import transaction
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_backend.settings')
django.setup()

from events.models import Event, Registration, User, UserProfile, Venue, EventCategory, University, WaitlistEntry
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

def setup_proper_test_data():
    """Setup test data with proper university associations"""
    # Clean up previous test data
    Registration.objects.all().delete()
    WaitlistEntry.objects.all().delete()
    Event.objects.all().delete()
    User.objects.filter(username__startswith='race_test_').delete()
    
    # Create Host University
    host_uni, _ = University.objects.get_or_create(
        name="Race Test University", 
        short_code="RTU", 
        domain="racetest.edu"
    )
    
    # Create Organizer from host university
    organizer, _ = User.objects.get_or_create(
        username="race_organizer", 
        defaults={'email': "organizer@racetest.edu"}
    )
    UserProfile.objects.get_or_create(
        user=organizer, 
        defaults={
            'university': host_uni, 
            'user_type': 'organizer',
            'is_verified': True
        }
    )
    
    # Create Venue & Category
    venue, _ = Venue.objects.get_or_create(
        name="Race Test Hall", 
        university=host_uni, 
        defaults={'capacity': 100}
    )
    category, _ = EventCategory.objects.get_or_create(name="Race Test Category")
    
    # Create Event with small capacity
    event = Event.objects.create(
        title="Race Condition Test Event - Fixed",
        description="Testing concurrent registrations with proper setup",
        date_time=timezone.now() + timezone.timedelta(days=30),
        venue=venue,
        organizer=organizer,
        host_university=host_uni,
        category=category,
        participant_limit=3,  # Very small limit to easily trigger race conditions
        visibility='university',  # Only host university students
        status='published'
    )
    
    return event, host_uni

def create_test_user(user_index, university):
    """Create test user properly associated with the university"""
    username = f"race_test_user_{user_index:02d}"
    email = f"{username}@{university.domain}"
    
    user, created = User.objects.get_or_create(
        username=username, 
        defaults={
            'email': email,
            'first_name': f"Test{user_index}",
            'last_name': "User"
        }
    )
    
    # Always update profile to ensure proper university association
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'university': university,
            'user_type': 'student',
            'is_verified': True
        }
    )
    
    # Ensure profile has correct university
    if profile.university != university:
        profile.university = university
        profile.save()
    
    return user

def attempt_registration_fixed(event_id, user_index, university):
    """Fixed registration attempt with proper error handling"""
    try:
        user = create_test_user(user_index, university)
        
        factory = APIRequestFactory()
        
        # Use the actual API endpoint
        from events.views import EventViewSet
        view = EventViewSet.as_view({'post': 'register'})
        
        request = factory.post(f'/api/events/{event_id}/register/')
        force_authenticate(request, user=user)
        
        response = view(request, pk=event_id)
        return response.status_code, response.data
        
    except Exception as e:
        return 500, {'error': str(e)}

def run_fixed_concurrent_test():
    """Run the fixed race condition test"""
    print("🚀 Starting Fixed Race Condition Test...")
    
    event, host_uni = setup_proper_test_data()
    print(f"✅ Created event: '{event.title}'")
    print(f"✅ Participant limit: {event.participant_limit}")
    print(f"✅ Host university: {host_uni.name}")
    print(f"✅ Event visibility: {event.visibility}")
    
    threads = []
    results = []
    lock = threading.Lock()
    
    def worker(i):
        # Small random delay to simulate real-world timing
        time.sleep(0.01 * (i % 5))
        code, data = attempt_registration_fixed(event.id, i, host_uni)
        
        with lock:
            results.append((i, code, data))
            status_msg = "✅ Registered" if code == 201 else "⏳ Waitlisted" if code == 200 and data.get('status') == 'added_to_waitlist' else "❌ Error"
            print(f"User {i:02d}: {status_msg} - {data}")

    # Launch more threads than capacity
    num_threads = 10
    print(f"\n🎯 Launching {num_threads} concurrent registration attempts for {event.participant_limit} spots...")
    
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Analyze results
    success_count = 0
    waitlist_count = 0
    error_count = 0
    other_count = 0
    
    print(f"\n📊 RESULTS ANALYSIS:")
    for i, code, data in results:
        if code == 201:
            success_count += 1
            print(f"  User {i:02d}: ✅ SUCCESS - Registered")
        elif code == 200 and data.get('status') == 'added_to_waitlist':
            waitlist_count += 1
            print(f"  User {i:02d}: ⏳ WAITLIST - Position {data.get('position')}")
        elif code >= 400:
            error_count += 1
            print(f"  User {i:02d}: ❌ ERROR {code} - {data}")
        else:
            other_count += 1
            print(f"  User {i:02d}: 🔄 OTHER {code} - {data}")
    
    # Verify database state
    with transaction.atomic():
        actual_registrations = Registration.objects.filter(
            event=event, 
            status='registered'
        ).count()
        
        actual_waitlist = WaitlistEntry.objects.filter(event=event).count()
    
    print(f"\n📈 SUMMARY:")
    print(f"  Successful Registrations: {success_count}")
    print(f"  Waitlisted Users: {waitlist_count}")
    print(f"  Errors: {error_count}")
    print(f"  Other Responses: {other_count}")
    
    print(f"\n🗄️ DATABASE STATE:")
    print(f"  Actual Registrations in DB: {actual_registrations}")
    print(f"  Actual Waitlist Entries in DB: {actual_waitlist}")
    
    # Race condition detection
    if actual_registrations > event.participant_limit:
        print(f"\n❌ CRITICAL: RACE CONDITION DETECTED!")
        print(f"   Limit: {event.participant_limit}, Actual: {actual_registrations}")
        print(f"   Overflow: {actual_registrations - event.participant_limit}")
    elif actual_registrations == event.participant_limit:
        print(f"\n✅ SUCCESS: Participant limit respected!")
        print(f"   All {actual_registrations} spots filled correctly")
    else:
        print(f"\n⚠️  WARNING: Limit not reached")
        print(f"   Expected: {event.participant_limit}, Got: {actual_registrations}")
        print(f"   This might indicate registration errors or test setup issues")

if __name__ == "__main__":
    run_fixed_concurrent_test()