import os
import django
from django.conf import settings
from django.db.models import Count

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_backend.settings')
django.setup()

from django.contrib.auth.models import User

def check_duplicates():
    print("Checking for duplicate emails...")
    duplicates = User.objects.values('email').annotate(count=Count('id')).filter(count__gt=1)
    
    if duplicates:
        print("Found duplicates:")
        for entry in duplicates:
            email = entry['email']
            count = entry['count']
            print(f"Email: {email}, Count: {count}")
            users = User.objects.filter(email=email)
            for u in users:
                print(f" - ID: {u.id}, Username: {u.username}")
    else:
        print("No duplicate emails found.")

if __name__ == "__main__":
    check_duplicates()
