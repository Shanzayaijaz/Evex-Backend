import os
import django
from django.conf import settings

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_backend.settings')
django.setup()

from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import User
from events.views import reset_password

def verify_reset_case_insensitive():
    print("Starting case-insensitive password reset verification...")

    # Setup - Ensure user exists with mixed case
    username_actual = 'ShaheerKhurrum'
    username_input = '  shaheerkhurrum  ' # Lowercase with spaces
    new_pass = 'new_pass_789'
    
    user, created = User.objects.get_or_create(username=username_actual)
    if created:
        user.email = 'k230749@nu.edu.pk'
        user.save()
        
    print(f"User exists: '{user.username}'")

    # Call Reset Endpoint with lowercase input
    factory = APIRequestFactory()
    request = factory.post('/api/events/reset-password/', {
        'username': username_input,
        'new_password': new_pass
    }, format='json')
    
    print(f"\nCalling reset-password endpoint with input: '{username_input}'")
    response = reset_password(request)
    print(f"Response Status: {response.status_code}")
    print(f"Response Data: {response.data}")

    if response.status_code == 200:
        # Verify New Password
        user.refresh_from_db()
        if user.check_password(new_pass):
            print("SUCCESS: Password updated successfully despite case mismatch.")
        else:
            print("FAILURE: Password was NOT updated.")
    else:
        print("FAILURE: Endpoint returned error.")

if __name__ == "__main__":
    try:
        verify_reset_case_insensitive()
    except Exception as e:
        print(f"Error: {e}")
