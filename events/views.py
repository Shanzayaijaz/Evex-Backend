from django.http import JsonResponse
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db.models import Q, Count, F
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import datetime, timedelta
from django.utils import timezone
from .models import *
from .serializers import *
from .utils import send_notification, promote_from_waitlist, get_user_profile

# Move IsOrganizerOrAdmin to the top, before any functions that use it
class IsOrganizerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user_profile = get_user_profile(request.user, create_if_missing=True)
        if not user_profile:
            return False
        return user_profile.user_type in ['organizer', 'admin'] or request.user.is_staff


class UsernameOrEmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the default SimpleJWT serializer to accept either username or email.
    """

    def validate(self, attrs):
        identifier = attrs.get(self.username_field)
        if identifier:
            UserModel = get_user_model()

            # Try to resolve the identifier to a username using email or case-insensitive username lookup
            user_lookup = None
            try:
                user_lookup = UserModel.objects.get(email__iexact=identifier)
            except UserModel.DoesNotExist:
                try:
                    user_lookup = UserModel.objects.get(username__iexact=identifier)
                except UserModel.DoesNotExist:
                    user_lookup = None

            if user_lookup:
                attrs[self.username_field] = user_lookup.get_username()

        return super().validate(attrs)


class UsernameOrEmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = UsernameOrEmailTokenObtainPairSerializer

# Add this registration function
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user with profile
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'user_type']
        for field in required_fields:
            if field not in data:
                return Response(
                    {'error': f'{field} is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if username already exists (case-insensitive)
        existing_user_by_username = User.objects.filter(username__iexact=data['username']).first()
        deleted_username_user_id = None
        if existing_user_by_username:
            # Check if this user has a profile by querying UserProfile directly
            has_profile = UserProfile.objects.filter(user=existing_user_by_username).exists()
            if has_profile:
                return Response(
                    {'error': 'Username already exists'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # User exists but has no profile - we can delete this orphaned user
                deleted_username_user_id = existing_user_by_username.id
                existing_user_by_username.delete()
        
        # Check if email already exists (case-insensitive)
        # Note: We check again in case it's a different user with the same email
        existing_user_by_email = User.objects.filter(email__iexact=data['email']).first()
        if existing_user_by_email:
            # Check if this user has a profile by querying UserProfile directly
            has_profile = UserProfile.objects.filter(user=existing_user_by_email).exists()
            if has_profile:
                return Response(
                    {'error': 'Email already exists'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # User exists but has no profile - we can delete this orphaned user
                # Only delete if it's not the same user we already deleted above
                if existing_user_by_email.id != deleted_username_user_id:
                    existing_user_by_email.delete()
        
        # For students, university is optional (can be set later in profile)
        # For organizers and admins, university is required
        university = None
        if data.get('university_id'):
            try:
                university = University.objects.get(id=data['university_id'])
            except University.DoesNotExist:
                return Response(
                    {'error': 'Invalid university ID'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif data['user_type'] in ['organizer', 'admin']:
            # Organizers and admins must have a university
            university = University.objects.first()
            if not university:
                return Response(
                    {'error': 'No universities available. Please contact administrator.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate user_type
        valid_user_types = ['student', 'organizer', 'admin']
        if data['user_type'] not in valid_user_types:
            return Response(
                {'error': f'Invalid user_type. Must be one of: {", ".join(valid_user_types)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user
        try:
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', '')
            )
        except IntegrityError as e:
            return Response(
                {'error': 'Username or email already exists'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValidationError as e:
            return Response(
                {'error': f'Validation error: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Error creating user: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user profile
        # Create or update user profile
        # Note: A signal might have already created the profile
        try:
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Update profile fields
            profile.university = university
            profile.user_type = data['user_type']
            profile.contact_number = data.get('contact_number', '')
            profile.department = data.get('department', '')
            # is_verified defaults to False in model, so we don't need to force it unless we want to reset it
            # profile.is_verified = False 
            profile.save()

        except Exception as e:
            # If profile update fails, delete the user to maintain consistency
            user.delete()
            return Response(
                {'error': f'Error creating/updating profile: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return user data
        user_data = UserSerializer(user).data
        
        return Response({
            'message': 'User registered successfully',
            'user': user_data,
            'profile': {
                'user_type': profile.user_type,
                'university': profile.university.name if profile.university else None,
                'is_verified': profile.is_verified
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Registration failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Add Analytics Endpoint
@api_view(['GET'])
@permission_classes([IsAdminUser])
def event_analytics(request):
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    
    # Basic stats
    total_events = Event.objects.count()
    published_events = Event.objects.filter(status='published').count()
    total_registrations = Registration.objects.filter(status='registered').count()
    total_users = User.objects.count()
    
    # User type breakdown
    student_count = UserProfile.objects.filter(user_type='student').count()
    organizer_count = UserProfile.objects.filter(user_type='organizer').count()
    admin_count = UserProfile.objects.filter(user_type='admin').count()
    
    # Recent activity (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_events = Event.objects.filter(created_at__gte=thirty_days_ago).count()
    recent_registrations = Registration.objects.filter(registered_at__gte=thirty_days_ago).count()
    
    # University stats
    university_stats = University.objects.annotate(
        event_count=Count('event', distinct=True),
        student_count=Count('userprofile', filter=Q(userprofile__user_type='student'), distinct=True)
    ).values('name', 'event_count', 'student_count')
    
    # Event category distribution
    category_stats = EventCategory.objects.annotate(
        event_count=Count('event')
    ).values('name', 'event_count')
    
    # Popular events (top 5 by registrations)
    popular_events = Event.objects.annotate(
        registration_count=Count('registration')
    ).order_by('-registration_count')[:5].values('title', 'registration_count')
    
    return Response({
        'overview': {
            'total_events': total_events,
            'published_events': published_events,
            'total_registrations': total_registrations,
            'total_users': total_users,
            'student_count': student_count,
            'organizer_count': organizer_count,
            'admin_count': admin_count,
            'recent_events': recent_events,
            'recent_registrations': recent_registrations,
        },
        'university_stats': list(university_stats),
        'category_stats': list(category_stats),
        'popular_events': list(popular_events),
    })

# Add Organizer Dashboard Endpoint
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard_overview(request):
    """
    Dashboard overview for students - returns recent activity and stats
    """
    user = request.user
    
    # Get 5 most recent activities
    recent_activities = RecentActivity.objects.filter(
        user=user
    ).select_related('event', 'user').order_by('-timestamp')[:5]
    
    # Get user's registrations for stats
    registrations = Registration.objects.filter(user=user).select_related('event')
    
    # Calculate stats
    now = timezone.now()
    upcoming_count = registrations.filter(
        status='registered',
        event__date_time__gte=now
    ).count()
    
    attended_count = registrations.filter(status='attended').count()
    
    total_registrations = registrations.count()
    attendance_rate = round((attended_count / total_registrations * 100) if total_registrations > 0 else 0)
    
    # Serialize recent activities
    activity_serializer = RecentActivitySerializer(recent_activities, many=True)
    
    return Response({
        'recent_activities': activity_serializer.data,
        'stats': {
            'upcoming_events': upcoming_count,
            'events_attended': attended_count,
            'attendance_rate': f"{attendance_rate}%",
            'total_registrations': total_registrations,
        }
    })

@api_view(['GET'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_dashboard(request):
    """
    Dashboard data for organizers
    """
    user = request.user
    # Get organizer's events
    organizer_events = Event.objects.filter(organizer=user)
    total_events = organizer_events.count()
    published_events = organizer_events.filter(status='published').count()
    draft_events = organizer_events.filter(status='draft').count()
    
    # Registration stats for organizer's events
    total_registrations = Registration.objects.filter(
        event__organizer=user, 
        status='registered'
    ).count()
    
    # Recent events (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_registrations = Registration.objects.filter(
        event__organizer=user,
        registered_at__gte=seven_days_ago
    ).count()
    
    # Upcoming events
    upcoming_events = organizer_events.filter(
        date_time__gte=datetime.now(),
        status='published'
    ).order_by('date_time')[:5]
    
    upcoming_events_data = EventSerializer(upcoming_events, many=True).data
    
    # Annotate registration counts to determine capacity status
    annotated_events = organizer_events.annotate(
        reg_count=Count('registration')
    )
    full_events_with_waitlist = annotated_events.filter(
        participant_limit__isnull=False,
        reg_count__gte=F('participant_limit')
    ).annotate(
        waitlist_count=Count('waitlistentry')
    ).filter(waitlist_count__gt=0)
    open_events = annotated_events.filter(
        participant_limit__isnull=False,
        reg_count__lt=F('participant_limit')
    )
    
    return Response({
        'overview': {
            'total_events': total_events,
            'published_events': published_events,
            'draft_events': draft_events,
            'total_registrations': total_registrations,
            'recent_registrations': recent_registrations,
            'open_events': open_events.count(),
        },
        'upcoming_events': upcoming_events_data,
        'full_events_count': full_events_with_waitlist.count(),
    })

@api_view(['GET'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_analytics(request):
    """
    Get analytics and notifications for organizer's events
    """
    user = request.user
    from django.db.models import Count, Q, F
    from datetime import datetime, timedelta
    
    # Get organizer's events
    organizer_events = Event.objects.filter(organizer=user)
    
    # Get notifications related to organizer's events
    notifications = Notification.objects.filter(
        related_event__organizer=user
    ).select_related('related_event', 'user').order_by('-created_at')[:50]
    
    notification_data = []
    for notif in notifications:
        notification_data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'notification_type': notif.notification_type,
            'is_read': notif.is_read,
            'created_at': notif.created_at,
            'event_id': notif.related_event.id if notif.related_event else None,
            'event_title': notif.related_event.title if notif.related_event else None,
            'user_name': notif.user.get_full_name() or notif.user.username,
            'user_email': notif.user.email,
        })
    
    # Get waitlist entries for full events
    full_events = organizer_events.annotate(
        reg_count=Count('registration', filter=Q(registration__status='registered'))
    ).filter(
        participant_limit__isnull=False,
        reg_count__gte=F('participant_limit')
    )
    
    waitlist_data = []
    for event in full_events:
        waitlist_entries = WaitlistEntry.objects.filter(
            event=event
        ).select_related('user__profile').order_by('position')
        
        for entry in waitlist_entries:
            profile = getattr(entry.user, 'profile', None)
            waitlist_data.append({
                'event_id': event.id,
                'event_title': event.title,
                'user_id': entry.user.id,
                'user_name': entry.user.get_full_name() or entry.user.username,
                'user_email': entry.user.email,
                'position': entry.position,
                'university': profile.university.name if (profile and profile.university) else None,
                'contact_number': getattr(profile, 'contact_number', '') if profile else '',
            })
    
    # Registration and cancellation stats
    total_registrations = Registration.objects.filter(
        event__organizer=user,
        status='registered'
    ).count()
    
    total_cancellations = Registration.objects.filter(
        event__organizer=user,
        status='cancelled'
    ).count()
    
    total_attended = Registration.objects.filter(
        event__organizer=user,
        status='attended'
    ).count()
    
    # Recent activity (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_registrations = Registration.objects.filter(
        event__organizer=user,
        status='registered',
        registered_at__gte=seven_days_ago
    ).count()
    
    recent_cancellations = Registration.objects.filter(
        event__organizer=user,
        status='cancelled',
        registered_at__gte=seven_days_ago
    ).count()
    
    return Response({
        'stats': {
            'total_registrations': total_registrations,
            'total_cancellations': total_cancellations,
            'total_attended': total_attended,
            'recent_registrations': recent_registrations,
            'recent_cancellations': recent_cancellations,
        },
        'notifications': notification_data,
        'waitlist': waitlist_data,
    })

@api_view(['GET'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_events(request):
    """
    List all events (including drafts) for the authenticated organizer
    """
    events = Event.objects.filter(
        organizer=request.user
    ).select_related('venue', 'host_university', 'category').order_by('-created_at')
    
    serializer = EventSerializer(events, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_mark_attendance(request, event_id):
    """
    Mark attendance for a user at an event (organizer only)
    """
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
    except Event.DoesNotExist:
        return Response(
            {'error': 'Event not found or you do not have permission'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    user_id = request.data.get('user_id')
    if not user_id:
        return Response(
            {'error': 'user_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user_to_mark = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if user is registered
    registration = Registration.objects.filter(
        event=event,
        user=user_to_mark,
        status__in=['registered', 'attended']
    ).first()
    
    if not registration:
        return Response(
            {'error': 'User must be registered for this event'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if already marked
    existing = Attendance.objects.filter(event=event, user=user_to_mark).first()
    if existing:
        return Response(
            {'error': 'Attendance already marked for this user'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create attendance
    attendance = Attendance.objects.create(
        event=event,
        user=user_to_mark,
        registration=registration,
        checked_in_by=request.user,
        notes=request.data.get('notes', '')
    )
    
    # Update registration status
    registration.status = 'attended'
    registration.save()
    
    serializer = AttendanceSerializer(attendance, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_event_attendance(request, event_id):
    """
    Get attendance list for a specific event (organizer only)
    """
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
    except Event.DoesNotExist:
        return Response(
            {'error': 'Event not found or you do not have permission'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    attendances = Attendance.objects.filter(event=event).select_related(
        'user__profile', 'checked_in_by'
    ).order_by('-checked_in_at')
    
    serializer = AttendanceSerializer(attendances, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_registrations(request):
    """
    Return registrations and attendance data for the organizer's events
    """
    events = Event.objects.filter(
        organizer=request.user
    ).select_related('venue').prefetch_related('registration_set__user__profile', 'waitlistentry_set__user__profile').order_by('date_time')
    
    response_data = []
    for event in events:
        registrations = list(
            event.registration_set.select_related('user__profile').order_by('-registered_at')
        )
        attended_count = sum(1 for reg in registrations if reg.status == 'attended')
        registration_data = []
        for reg in registrations:
            profile = getattr(reg.user, 'profile', None)
            university_name = profile.university.name if (profile and profile.university) else None
            registration_data.append({
                'id': reg.id,
                'status': reg.status,
                'registered_at': reg.registered_at,
                'user': {
                    'id': reg.user.id,
                    'name': reg.user.get_full_name() or reg.user.username,
                    'email': reg.user.email,
                    'university': university_name,
                    'contact_number': getattr(profile, 'contact_number', '') if profile else '',
                }
            })
        
        # Get waitlist entries if event is full
        waitlist_data = []
        if event.is_full:
            waitlist_entries = event.waitlistentry_set.select_related('user__profile').order_by('position')
            for entry in waitlist_entries:
                profile = getattr(entry.user, 'profile', None)
                waitlist_data.append({
                    'id': entry.id,
                    'position': entry.position,
                    'joined_at': entry.joined_at,
                    'user': {
                        'id': entry.user.id,
                        'name': entry.user.get_full_name() or entry.user.username,
                        'email': entry.user.email,
                        'university': profile.university.name if (profile and profile.university) else None,
                        'contact_number': getattr(profile, 'contact_number', '') if profile else '',
                    }
                })
        
        response_data.append({
            'id': event.id,
            'title': event.title,
            'date_time': event.date_time,
            'venue_name': event.venue.name if event.venue else None,
            'participant_limit': event.participant_limit,
            'registered_count': event.registered_count,
            'attended_count': attended_count,
            'status': event.status,
            'is_full': event.is_full,
            'registrations': registration_data,
            'waitlist': waitlist_data,
        })
    
    return Response({'events': response_data})


@api_view(['GET'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_get_event(request, event_id):
    """
    Get a single event by ID for the authenticated organizer
    """
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
        serializer = EventSerializer(event, context={'request': request})
        return Response(serializer.data)
    except Event.DoesNotExist:
        return Response(
            {'error': 'Event not found or you do not have permission to view it'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['PUT', 'PATCH'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_update_event(request, event_id):
    """
    Update an event for the authenticated organizer
    """
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
    except Event.DoesNotExist:
        return Response(
            {'error': 'Event not found or you do not have permission to edit it'},
            status=status.HTTP_404_NOT_FOUND
        )

    data = request.data
    profile = get_user_profile(request.user, create_if_missing=False)
    if not profile or not profile.university:
        return Response(
            {'error': 'Please set your university in your profile settings'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Update basic fields
    if 'title' in data:
        event.title = data.get('title').strip()
    if 'description' in data:
        event.description = data.get('description')
    if 'participant_limit' in data:
        event.participant_limit = int(data.get('participant_limit'))
    if 'status' in data:
        event.status = data.get('status')
    if 'visibility' in data:
        visibility = data.get('visibility')
        if visibility in dict(Event.EVENT_VISIBILITY).keys():

            event.visibility = visibility
            
            # Handle allowed universities if switching to/updating inter-university
            if visibility == 'inter_university' and 'allowed_universities' in data:
                allowed_ids = data.get('allowed_universities', [])
                if allowed_ids:
                    universities = University.objects.filter(id__in=allowed_ids)
                    event.allowed_universities.set(universities)
                else:
                    event.allowed_universities.clear()
            elif visibility != 'inter_university':
                # Clear allowed universities if not inter-university
                event.allowed_universities.clear()

    # Update date/time
    if 'date' in data and 'time' in data:
        try:
            date_str = data.get('date')
            time_str = data.get('time')
            event_datetime = timezone.make_aware(
                datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            )
            event.date_time = event_datetime
        except Exception:
            return Response(
                {'error': 'Invalid date or time provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Update category
    if 'category' in data:
        category_name = data.get('category').strip()
        category, _ = EventCategory.objects.get_or_create(name=category_name)
        event.category = category

    # Update venue
    if 'location' in data:
        venue_name = data.get('location').strip()
        venue, _ = Venue.objects.get_or_create(
            name=venue_name,
            university=profile.university,
            defaults={'capacity': event.participant_limit, 'features': {}}
        )
        event.venue = venue

    event.save()
    serializer = EventSerializer(event, context={'request': request})
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsOrganizerOrAdmin])
def organizer_create_event(request):
    """
    Create a new event using simplified organizer form data.
    """
    data = request.data
    profile = get_user_profile(request.user, create_if_missing=True)

    if not profile or not profile.university:
        return Response(
            {'error': 'Please set your university in your profile before creating events.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    required_fields = ['title', 'description', 'date', 'time', 'location', 'capacity', 'category']
    missing = [field for field in required_fields if not str(data.get(field, '')).strip()]
    if missing:
        return Response(
            {'error': f"Missing required fields: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        capacity = int(data.get('capacity'))
        if capacity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {'error': 'Capacity must be a positive integer.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        event_datetime = timezone.make_aware(
            datetime.strptime(f"{data.get('date')} {data.get('time')}", "%Y-%m-%d %H:%M")
        )
    except Exception:
        return Response(
            {'error': 'Invalid date or time provided.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    category_name = data.get('category').strip()
    category, _ = EventCategory.objects.get_or_create(name=category_name)

    venue_name = data.get('location').strip()
    venue, _ = Venue.objects.get_or_create(
        name=venue_name,
        university=profile.university,
        defaults={'capacity': capacity, 'features': {}}
    )

    visibility = data.get('visibility', 'university')
    valid_visibility = dict(Event.EVENT_VISIBILITY).keys()
    if visibility not in valid_visibility:
        visibility = 'university'

    status_value = 'published' if data.get('status') == 'published' else 'draft'

    event = Event.objects.create(
        title=data.get('title').strip(),
        description=data.get('description'),
        date_time=event_datetime,
        venue=venue,
        organizer=request.user,
        host_university=profile.university,
        category=category,
        participant_limit=capacity,
        visibility=visibility,
        status=status_value
    )

    price = data.get('price')
    tags = data.get('tags')
    extra_sections = []
    
    # Handle allowed universities for inter-university events
    if visibility == 'inter_university':
        allowed_ids = data.get('allowed_universities', [])
        if allowed_ids:
            try:
                universities = University.objects.filter(id__in=allowed_ids)
                event.allowed_universities.set(universities)
            except Exception:
                pass # Ignore invalid IDs
    if price not in [None, '']:
        extra_sections.append(f"Ticket Price: PKR {price}")
    if tags:
        extra_sections.append(f"Tags: {tags}")
    if extra_sections:
        event.description = f"{event.description}\n\n" + "\n".join(extra_sections)
        event.save(update_fields=['description'])

    serializer = EventSerializer(event, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)

# Your existing ViewSets continue below...
class UniversityViewSet(viewsets.ModelViewSet):
    queryset = University.objects.filter(is_active=True)
    serializer_class = UniversitySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()

class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return UserProfile.objects.all()
        return UserProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user with profile"""
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_serializer = UserSerializer(request.user)
            profile_serializer = UserProfileSerializer(profile)
            return Response({
                'user': user_serializer.data,
                'profile': profile_serializer.data
            })
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['patch', 'put'])
    def update_me(self, request):
        """Update current user's profile"""
        try:
            profile = UserProfile.objects.get(user=request.user)
            user = request.user
            
            # Update user fields
            if 'first_name' in request.data:
                user.first_name = request.data['first_name']
            if 'last_name' in request.data:
                user.last_name = request.data['last_name']
            user.save()
            
            # Update profile fields
            if 'contact_number' in request.data:
                profile.contact_number = request.data['contact_number'] or ''
            if 'department' in request.data:
                profile.department = request.data['department'] or ''
            if 'university' in request.data:
                university_id = request.data['university']
                if university_id:
                    try:
                        profile.university = University.objects.get(id=university_id)
                    except University.DoesNotExist:
                        return Response({'error': 'Invalid university ID'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    profile.university = None
            profile.save()
            
            # Return updated data
            user_serializer = UserSerializer(user)
            profile_serializer = UserProfileSerializer(profile)
            return Response({
                'user': user_serializer.data,
                'profile': profile_serializer.data
            })
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['delete'])
    def delete_me(self, request):
        """Delete current user's account"""
        try:
            user = request.user
            user.delete()
            return Response({'message': 'User account deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.filter(is_active=True)
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticated]

class EventCategoryViewSet(viewsets.ModelViewSet):
    queryset = EventCategory.objects.all()
    serializer_class = EventCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        # Allow unauthenticated access to list and retrieve actions for public events
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsOrganizerOrAdmin()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        queryset = Event.objects.filter(status='published')
        # Search and filter parameters
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        university = self.request.query_params.get('university')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(description__icontains=search)
            )
        if category:
            queryset = queryset.filter(category_id=category)
        if university:
            queryset = queryset.filter(host_university_id=university)
        if date_from:
            queryset = queryset.filter(date_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_time__date__lte=date_to)
            
        return queryset.order_by('date_time')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=True, methods=['post'])
    def register(self, request, pk=None):
        user = request.user
        
        # Ensure user has a profile
        user_profile = get_user_profile(user, create_if_missing=True)
        
        try:
            with transaction.atomic():
                # Lock the event to prevent race conditions on capacity
                try:
                    event = Event.objects.select_for_update().get(pk=pk)
                except Event.DoesNotExist:
                    return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)

                # 🔹 1. Check university restrictions
                if event.visibility == 'university':
                    if user_profile.university != event.host_university:
                        return Response(
                            {'error': 'This event is only for students of the host university'}, 
                            status=status.HTTP_403_FORBIDDEN
                        )
                elif event.visibility == 'inter_university':
                    allowed_universities = event.allowed_universities.all()
                    if allowed_universities.exists() and user_profile.university not in allowed_universities:
                        return Response(
                            {'error': 'Your university is not allowed to register for this event'}, 
                            status=status.HTTP_403_FORBIDDEN
                        )

                # 🔹 2. Check for time clashes with other registered events
                EVENT_DURATION_HOURS = 2
                new_event_start = event.date_time
                new_event_end = event.date_time + timedelta(hours=EVENT_DURATION_HOURS)
                
                # Get all active registrations for this user
                user_registrations = Registration.objects.filter(
                    user=user,
                    status__in=['registered', 'attended']
                ).select_related('event')
                
                for reg in user_registrations:
                    existing_event = reg.event
                    # Skip if it's the same event
                    if existing_event.id == event.id:
                        continue
                        
                    existing_start = existing_event.date_time
                    existing_end = existing_event.date_time + timedelta(hours=EVENT_DURATION_HOURS)
                    
                    # Check overlap: (StartA < EndB) and (EndA > StartB)
                    if new_event_start < existing_end and new_event_end > existing_start:
                        return Response(
                            {'error': f'Time clash with registered event: {existing_event.title}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                # 🔹 2. Check if user is in waitlist
                if WaitlistEntry.objects.filter(event=event, user=user).exists():
                    return Response(
                        {'error': 'You are already on the waitlist for this event'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 🔹 3. Check capacity and handle registration
                if event.is_full:
                    # Check if already registered before adding to waitlist
                    if Registration.objects.filter(event=event, user=user, status='registered').exists():
                        return Response(
                            {'error': 'Already registered for this event'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                        
                    # Add to waitlist
                    position = WaitlistEntry.objects.filter(event=event).count() + 1
                    WaitlistEntry.objects.create(event=event, user=user, position=position)
                    
                    user_name = user.get_full_name() or user.username
                    send_notification(
                        user=user,
                        title="Added to Waitlist",
                        message=f"{user_name} has been added to waitlist for {event.title} (Position: {position})",
                        notification_type='waitlist_promotion',
                        related_event=event
                    )
                    
                    # Log Activity
                    RecentActivity.objects.create(
                        user=user,
                        event=event,
                        action='waitlisted'
                    )
                    
                    return Response({'status': 'added_to_waitlist', 'position': position})
                
                else:
                    # Event is not full, attempt registration
                    # Use get_or_create to handle concurrent requests from same user
                    registration, created = Registration.objects.get_or_create(
                        event=event,
                        user=user,
                        defaults={'status': 'registered'}
                    )
                    
                    if not created:
                        # If registration exists, check its status
                        if registration.status == 'registered':
                            return Response(
                                {'error': 'Already registered for this event'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        elif registration.status == 'cancelled':
                            # Reactivate cancelled registration
                            registration.status = 'registered'
                            registration.save()
                        elif registration.status == 'waitlisted':
                            registration.status = 'registered'
                            registration.save()
                            
                    # Create RecentActivity entry
                    RecentActivity.objects.create(
                        user=user,
                        event=event,
                        action='registered'
                    )
                    
                    user_name = user.get_full_name() or user.username
                    send_notification(
                        user=user,
                        title="Registration Confirmation",
                        message=f"{user_name} has successfully registered for {event.title}",
                        notification_type='registration_confirmation',
                        related_event=event
                    )
                    
                    serializer = RegistrationSerializer(registration)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_destroy(self, instance):
        """Soft delete: mark as cancelled instead of deleting"""
        instance.status = 'cancelled'
        instance.save()

    @action(detail=True, methods=['post'])
    def cancel_registration(self, request, pk=None):
        event = self.get_object()
        user = request.user
        
        registration = Registration.objects.filter(event=event, user=user).first()
        if not registration:
            return Response(
                {'error': 'Not registered for this event'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        registration.status = 'cancelled'
        registration.save()
        
        # Create RecentActivity entry for cancellation
        RecentActivity.objects.create(
            user=user,
            event=event,
            action='cancelled'
        )
        
        # Promote from waitlist
        promote_from_waitlist(event)
        
        user_name = user.get_full_name() or user.username
        send_notification(
            user=user,
            title="Registration Cancelled",
            message=f"{user_name}'s registration for {event.title} has been cancelled",
            notification_type='event_cancelled',
            related_event=event
        )
        
        return Response({'status': 'registration_cancelled'})

# FIXED ViewSets with queryset defined
class RegistrationViewSet(viewsets.ModelViewSet):
    serializer_class = RegistrationSerializer
    permission_classes = [IsAuthenticated]
    
    # Add queryset at class level
    queryset = Registration.objects.all()

    def get_queryset(self):
        return Registration.objects.filter(user=self.request.user)

class WaitlistEntryViewSet(viewsets.ModelViewSet):
    serializer_class = WaitlistEntrySerializer
    permission_classes = [IsAuthenticated]
    
    # Add queryset at class level
    queryset = WaitlistEntry.objects.all()

    def get_queryset(self):
        return WaitlistEntry.objects.filter(user=self.request.user)

class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    
    queryset = Attendance.objects.all()
    
    def get_queryset(self):
        user = self.request.user
        user_profile = get_user_profile(user, create_if_missing=False)
        
        # Admin can see all attendance
        if user.is_staff or (user_profile and user_profile.user_type == 'admin'):
            return Attendance.objects.all().select_related('event', 'user', 'registration', 'checked_in_by')
        
        # Organizer can see attendance for their events
        if user_profile and user_profile.user_type == 'organizer':
            return Attendance.objects.filter(
                event__organizer=user
            ).select_related('event', 'user', 'registration', 'checked_in_by')
        
        # Students can only see their own attendance
        return Attendance.objects.filter(user=user).select_related('event', 'user', 'registration', 'checked_in_by')
    
    def get_permissions(self):
        # Only allow create/update/delete for organizers and admins
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsOrganizerOrAdmin()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Mark attendance - creates Attendance record and updates Registration status"""
        event = serializer.validated_data['event']
        user_to_mark = serializer.validated_data['user']
        request_user = self.request.user
        
        # Verify organizer owns the event or user is admin
        user_profile = get_user_profile(request_user, create_if_missing=False)
        if not (request_user.is_staff or (user_profile and user_profile.user_type == 'admin')):
            if event.organizer != request_user:
                raise ValidationError({'error': 'You can only mark attendance for your own events'})
        
        # Check if user is registered for the event
        registration = Registration.objects.filter(
            event=event,
            user=user_to_mark,
            status__in=['registered', 'attended']
        ).first()
        
        if not registration:
            raise ValidationError({
                'user': 'User must be registered for this event to mark attendance'
            })
        
        # Check if attendance already exists
        existing_attendance = Attendance.objects.filter(event=event, user=user_to_mark).first()
        if existing_attendance:
            raise ValidationError({
                'user': 'Attendance already marked for this user'
            })
        
        # Create attendance record
        attendance = serializer.save(
            registration=registration,
            checked_in_by=request_user
        )
        
        # Update registration status to 'attended'
        registration.status = 'attended'
        registration.save()
        
        # Send notification
        user_name = user_to_mark.get_full_name() or user_to_mark.username
        send_notification(
            user=user_to_mark,
            title="Attendance Confirmed",
            message=f"{user_name}'s attendance has been confirmed for {event.title}",
            notification_type='registration_confirmation',
            related_event=event
        )
        
        return attendance

class FeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]
    
    # Add queryset at class level
    queryset = Feedback.objects.all()

    def get_queryset(self):
        return Feedback.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Validate that the user has attended the event
        event = serializer.validated_data['event']
        user = self.request.user
        
        # Check if user has an attendance record for this event
        attendance = Attendance.objects.filter(
            event=event,
            user=user
        ).first()
        
        if not attendance:
            raise ValidationError({
                'event': ['You can only provide feedback for events you have attended.']
            })
        
        # Check if feedback already exists
        existing_feedback = Feedback.objects.filter(
            event=event,
            user=user
        ).first()
        
        if existing_feedback:
            raise ValidationError({
                'event': ['You have already submitted feedback for this event.']
            })
        
        serializer.save(user=user)
    
    @action(detail=False, methods=['get'])
    def attended_events(self, request):
        """Get events that the user has attended (has Attendance record)"""
        attendances = Attendance.objects.filter(
            user=request.user
        ).select_related('event').order_by('-event__date_time')
        
        # Check which events already have feedback
        feedback_events = set(
            Feedback.objects.filter(user=request.user).values_list('event_id', flat=True)
        )
        
        events_data = []
        for attendance in attendances:
            events_data.append({
                'id': attendance.event.id,
                'title': attendance.event.title,
                'date_time': attendance.event.date_time,
                'checked_in_at': attendance.checked_in_at,
                'has_feedback': attendance.event.id in feedback_events
            })
        
        return Response(events_data, status=status.HTTP_200_OK)

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    # Add queryset at class level
    queryset = Notification.objects.all()

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'all_notifications_marked_read'})

# Admin-only endpoints
class AdminEventViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = EventSerializer
    
    def get_queryset(self):
        queryset = Event.objects.all()
        
        # Filter by university
        university_id = self.request.query_params.get('university', None)
        if university_id and university_id != 'all':
            queryset = queryset.filter(host_university_id=university_id)
            
        # Filter by status
        status_param = self.request.query_params.get('status', None)
        if status_param and status_param != 'all':
            queryset = queryset.filter(status=status_param)
            
        return queryset.order_by('-date_time')



class AdminUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    
    def get_queryset(self):
        # Use select_related for profile to avoid N+1 queries
        # Note: select_related works with nullable ForeignKeys (profile can be None)
        return User.objects.select_related('profile').all()
    
    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in AdminUserViewSet.list: {str(e)}", exc_info=True)
            from rest_framework.response import Response
            from rest_framework import status
            return Response(
                {'error': f'Error fetching users: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AdminUniversityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
