import os
import django
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campus_event_manager.settings')
django.setup()

User = get_user_model()

def verify_analytics():
    print("Verifying Analytics Endpoint...")
    
    # Create an admin user to access the endpoint
    admin_user, created = User.objects.get_or_create(username='admin_test', email='admin@test.com')
    if created:
        admin_user.set_password('password')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        
    client = APIClient()
    client.force_authenticate(user=admin_user)
    
    response = client.get('/api/events/analytics/')
    
    if response.status_code == 200:
        print("Analytics Endpoint: OK")
        data = response.data
        print(f"Total Students: {data['overview']['student_count']}")
        print("University Stats:")
        for uni in data['university_stats']:
            print(f"- {uni['name']}: {uni['student_count']} students")
    else:
        print(f"Failed to fetch analytics: {response.status_code}")
        print(response.data)

if __name__ == '__main__':
    verify_analytics()
