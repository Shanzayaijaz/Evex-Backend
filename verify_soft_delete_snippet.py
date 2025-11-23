from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from events.models import Event, University, Venue, EventCategory
from django.conf import settings

# Ensure testserver is allowed
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS += ['testserver']

User = get_user_model()

print("Verifying Soft Delete...")

# Setup data
admin_user, _ = User.objects.get_or_create(username='admin_delete_test', email='admin_delete@test.com')
admin_user.set_password('password')
admin_user.is_staff = True
admin_user.is_superuser = True
admin_user.save()

uni, _ = University.objects.get_or_create(name="Uni Delete", short_code="UD", domain="ud.edu")
venue, _ = Venue.objects.get_or_create(name="Delete Venue", university=uni, capacity=100)
category, _ = EventCategory.objects.get_or_create(name="Delete Category")

# Create event to delete
event = Event.objects.create(
    title="Event to Delete", description="Desc", date_time=timezone.now() + timedelta(days=1),
    venue=venue, organizer=admin_user, host_university=uni, category=category,
    participant_limit=10, status='published'
)
event_id = event.id

client = APIClient()
client.force_authenticate(user=admin_user)

# Perform DELETE
print(f"Deleting event ID: {event_id}")
response = client.delete(f'/api/admin/events/{event_id}/')

if response.status_code == 204:
    print("DELETE request successful (204 No Content)")
    
    # Verify event still exists and status is cancelled
    try:
        updated_event = Event.objects.get(id=event_id)
        print(f"Event status after delete: {updated_event.status}")
        if updated_event.status == 'cancelled':
            print("SUCCESS: Event was soft deleted (marked as cancelled)")
        else:
            print(f"FAIL: Event status is {updated_event.status}, expected 'cancelled'")
    except Event.DoesNotExist:
        print("FAIL: Event was permanently deleted from database")
else:
    print(f"FAIL: DELETE request failed with status {response.status_code}")
    print(response.content)
