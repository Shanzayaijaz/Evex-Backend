import requests

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "123"

def test_api():
    print("🔐 Testing API with your credentials...")
    print(f"Username: {USERNAME}")
    print(f"Password: {PASSWORD}")
    
    # Step 1: Get JWT Token
    print("\n1. Getting JWT Token...")
    try:
        token_response = requests.post(
            f"{BASE_URL}/api/token/",
            json={"username": USERNAME, "password": PASSWORD}
        )
        
        if token_response.status_code != 200:
            print(f"❌ Token request failed: {token_response.text}")
            return None
        
        tokens = token_response.json()
        access_token = tokens['access']
        refresh_token = tokens['refresh']
        print(f"✅ Token obtained successfully!")
        print(f"Access Token: {access_token[:50]}...")
        return access_token
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_endpoints(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Step 2: Test Universities API
    print("\n2. Testing Universities API...")
    try:
        uni_response = requests.get(f"{BASE_URL}/api/universities/", headers=headers)
        
        if uni_response.status_code == 200:
            universities = uni_response.json()
            print(f"✅ Universities retrieved: {len(universities)} found")
            for uni in universities:
                print(f"   - {uni['name']} ({uni['short_code']})")
        else:
            print(f"❌ Universities request failed: {uni_response.status_code} - {uni_response.text}")
    except Exception as e:
        print(f"❌ Error testing universities: {e}")
    
    # Step 3: Test Events API
    print("\n3. Testing Events API...")
    try:
        events_response = requests.get(f"{BASE_URL}/api/events/", headers=headers)
        
        if events_response.status_code == 200:
            events = events_response.json()
            print(f"✅ Events retrieved: {len(events)} found")
            for event in events:
                print(f"   - {event['title']} (Status: {event.get('status', 'N/A')})")
        else:
            print(f"❌ Events request failed: {events_response.status_code} - {events_response.text}")
    except Exception as e:
        print(f"❌ Error testing events: {e}")
    
    # Step 4: Test User Profile
    print("\n4. Testing User Profile...")
    try:
        profile_response = requests.get(f"{BASE_URL}/api/profiles/", headers=headers)
        
        if profile_response.status_code == 200:
            profiles = profile_response.json()
            print(f"✅ Profiles retrieved: {len(profiles)} found")
            for profile in profiles:
                print(f"   - User Type: {profile.get('user_type', 'N/A')}")
                print(f"   - University: {profile.get('university_name', 'N/A')}")
        else:
            print(f"❌ Profile request failed: {profile_response.status_code} - {profile_response.text}")
    except Exception as e:
        print(f"❌ Error testing profiles: {e}")

if __name__ == "__main__":
    access_token = test_api()
    if access_token:
        test_endpoints(access_token)
    else:
        print("\n💡 If authentication failed, you might need to:")
        print("   1. Check if the user 'admin' exists")
        print("   2. Create a new superuser: python manage.py createsuperuser")
        print("   3. Or create a test user using the methods mentioned earlier")