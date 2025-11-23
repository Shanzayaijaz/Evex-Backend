from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from django.conf import settings
settings.ALLOWED_HOSTS += ['testserver']

User = get_user_model()

print("Verifying Analytics Endpoint...")

# Create an admin user to access the endpoint
admin_user, created = User.objects.get_or_create(username='admin_test_shell', email='admin_shell@test.com')
admin_user.set_password('password')
admin_user.is_staff = True
admin_user.is_superuser = True
admin_user.save()
    
client = APIClient()
client.force_authenticate(user=admin_user)

response = client.get('/api/analytics/')

if response.status_code == 200:
    print("Analytics Endpoint: OK")
    data = response.data
    print(f"Total Students: {data['overview']['student_count']}")
    print("University Stats:")
    for uni in data['university_stats']:
        print(f"- {uni['name']}: {uni['student_count']} students")
    import re
    content = response.content.decode('utf-8')
    match = re.search(r'<pre class="exception_value">(.*?)</pre>', content, re.DOTALL)
    if match:
        print(f"Exception: {match.group(1)}")
    else:
        print("Could not find exception in HTML")
        print(content[:500])
