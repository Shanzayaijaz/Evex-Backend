import os
import django
from django.conf import settings

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_backend.settings')
django.setup()

from django.contrib.auth.models import User

def check_user():
    username_input = "ShaheerKhurrum"
    print(f"Checking for user: '{username_input}'")

    # Check exact match
    try:
        user = User.objects.get(username=username_input)
        print(f"FOUND (Exact match): ID={user.id}, Username='{user.username}', Email='{user.email}'")
    except User.DoesNotExist:
        print("NOT FOUND (Exact match)")

    # Check case-insensitive match
    try:
        user = User.objects.get(username__iexact=username_input)
        print(f"FOUND (Case-insensitive match): ID={user.id}, Username='{user.username}', Email='{user.email}'")
    except User.DoesNotExist:
        print("NOT FOUND (Case-insensitive match)")
    except User.MultipleObjectsReturned:
        print("MULTIPLE FOUND (Case-insensitive match)")

if __name__ == "__main__":
    check_user()
