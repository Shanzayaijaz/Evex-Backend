from rest_framework import serializers
from django.contrib.auth.models import User
from .models import *

class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
    university_name = serializers.SerializerMethodField()
    university_domain = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = '__all__'
    
    def get_university_name(self, obj):
        return obj.university.name if obj.university else None
    
    def get_university_domain(self, obj):
        return obj.university.domain if obj.university else None

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile', 'user_type']

    def to_representation(self, instance):
        representation = {
            'id': instance.id,
            'username': instance.username,
            'email': instance.email,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'profile': None,
            'user_type': None,
        }

        # Safely try to access and serialize profile
        profile_instance = getattr(instance, 'profile', None)
        if profile_instance:
            try:
                representation['profile'] = UserProfileSerializer(profile_instance).data
                representation['user_type'] = profile_instance.user_type
            except Exception:
                # If any error occurs (serialization error etc.), keep defaults.
                pass

        return representation

class VenueSerializer(serializers.ModelSerializer):
    university_name = serializers.CharField(source='university.name', read_only=True)
    
    class Meta:
        model = Venue
        fields = '__all__'

class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = '__all__'

class EventSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    university_name = serializers.CharField(source='host_university.name', read_only=True)
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    registered_count = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    user_registration_status = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField() 
    class Meta:
        model = Event
        fields = '__all__'
    
    def get_user_registration_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            registration = Registration.objects.filter(event=obj, user=request.user).first()
            return registration.status if registration else None
        return None
    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None
    
class RegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    event = EventSerializer(read_only=True)
    
    class Meta:
        model = Registration
        fields = '__all__'

class WaitlistEntrySerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = WaitlistEntry
        fields = '__all__'

class AttendanceSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_date = serializers.DateTimeField(source='event.date_time', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    checked_in_by_name = serializers.CharField(source='checked_in_by.get_full_name', read_only=True)
    registration_status = serializers.CharField(source='registration.status', read_only=True)
    
    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['checked_in_at']

class FeedbackSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Feedback
        fields = '__all__'
        read_only_fields = ['user', 'created_at']
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

class NotificationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='related_event.title', read_only=True)
    
    class Meta:
        model = Notification
        fields = '__all__'

class RecentActivitySerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_id = serializers.IntegerField(source='event.id', read_only=True)
    event_date = serializers.DateTimeField(source='event.date_time', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = RecentActivity
        fields = ['id', 'user', 'event', 'event_id', 'event_title', 'event_date', 'action', 'timestamp', 'user_name']
        read_only_fields = ['timestamp']