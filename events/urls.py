from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'universities', views.UniversityViewSet, basename='university')
router.register(r'profiles', views.UserProfileViewSet, basename='profile')
router.register(r'venues', views.VenueViewSet, basename='venue')
router.register(r'categories', views.EventCategoryViewSet, basename='category')
router.register(r'events', views.EventViewSet, basename='event')
router.register(r'registrations', views.RegistrationViewSet, basename='registration')
router.register(r'waitlist', views.WaitlistEntryViewSet, basename='waitlist')
router.register(r'attendance', views.AttendanceViewSet, basename='attendance')
router.register(r'feedback', views.FeedbackViewSet, basename='feedback')
router.register(r'notifications', views.NotificationViewSet, basename='notification')

# Admin routes
router.register(r'admin/events', views.AdminEventViewSet, basename='admin-event')
router.register(r'admin/users', views.AdminUserViewSet, basename='admin-user')
router.register(r'admin/universities', views.AdminUniversityViewSet, basename='admin-university')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', views.register_user, name='register'),
    path('analytics/', views.event_analytics, name='analytics'),
    path('health/', views.health_check, name='health_check'),
    path('student/overview/', views.student_dashboard_overview, name='student-dashboard-overview'),
    path('organizer/dashboard/', views.organizer_dashboard, name='organizer-dashboard'),
    path('organizer/analytics/', views.organizer_analytics, name='organizer-analytics'),
    path('organizer/events/', views.organizer_events, name='organizer-events'),
    path('organizer/events/<int:event_id>/', views.organizer_get_event, name='organizer-get-event'),
    path('organizer/events/<int:event_id>/update/', views.organizer_update_event, name='organizer-update-event'),
    path('organizer/events/<int:event_id>/attendance/', views.organizer_event_attendance, name='organizer-event-attendance'),
    path('organizer/events/<int:event_id>/mark-attendance/', views.organizer_mark_attendance, name='organizer-mark-attendance'),
    path('organizer/create-event/', views.organizer_create_event, name='organizer-create-event'),
    path('organizer/registrations/', views.organizer_registrations, name='organizer-registrations'),
]
