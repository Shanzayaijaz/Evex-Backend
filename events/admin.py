from django.contrib import admin
from .models import *

@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_code', 'domain', 'is_active']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'university', 'user_type', 'is_verified']

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'university', 'capacity', 'is_active']

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'organizer', 'host_university', 'date_time', 'status']
    list_filter = ['status', 'host_university', 'category']

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'status', 'registered_at']

admin.site.register([EventCategory, WaitlistEntry, Attendance, Feedback, Notification])