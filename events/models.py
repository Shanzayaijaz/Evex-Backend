from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta  # ADD THIS IMPORT

class University(models.Model):
    name = models.CharField(max_length=200)
    short_code = models.CharField(max_length=10)
    domain = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='university_logos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    USER_TYPES = (
        ('student', 'Student'),
        ('organizer', 'Event Organizer'),
        ('admin', 'System Admin'),
    )
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        related_query_name='profile'
    )
    university = models.ForeignKey(University, on_delete=models.SET_NULL, null=True, blank=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='student')
    student_id = models.CharField(max_length=50, blank=True)
    contact_number = models.CharField(max_length=15, blank=True)
    department = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        university_name = self.university.name if self.university else "No University"
        return f"{self.user.email} - {university_name}"

class Venue(models.Model):
    name = models.CharField(max_length=200)
    university = models.ForeignKey(University, on_delete=models.CASCADE)
    capacity = models.IntegerField()
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.university.short_code}"

class EventCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Event(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    )
    
    EVENT_VISIBILITY = (
        ('university', 'My University Only'),
        ('inter_university', 'All Universities'),
        ('public', 'Public Event'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    date_time = models.DateTimeField()
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    host_university = models.ForeignKey(University, on_delete=models.CASCADE)
    category = models.ForeignKey(EventCategory, on_delete=models.PROTECT)
    participant_limit = models.IntegerField()
    visibility = models.CharField(max_length=20, choices=EVENT_VISIBILITY, default='university')
    allowed_universities = models.ManyToManyField(University, related_name='allowed_events', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='event_images/', null=True, blank=True)
    def clean(self):
        # Clash detection
        if self.status == 'published' and self.venue:
            clashes = Event.objects.filter(
                venue=self.venue,
                date_time__date=self.date_time.date(),
                status='published'
            ).exclude(pk=self.pk)
            
            for clash in clashes:
                # Assume events are 2 hours long for clash detection
                event_end = clash.date_time + timedelta(hours=2)
                if self.date_time < event_end:
                    raise ValidationError(f"Venue clash with event: {clash.title}")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def registered_count(self):
        return self.registration_set.filter(status='registered').count()
    
    @property
    def is_full(self):
        """
        Determine if the event has reached its capacity.
        """
        if self.participant_limit is None:
            return False
        return self.registration_set.filter(status__in=['registered', 'attended']).count() >= self.participant_limit

class Registration(models.Model):
    REG_STATUS = (
        ('registered', 'Registered'),
        ('cancelled', 'Cancelled'),
        ('attended', 'Attended'),
        ('waitlisted', 'Waitlisted'),
    )
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=REG_STATUS, default='registered')

    class Meta:
        unique_together = ['event', 'user']
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"

class WaitlistEntry(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    position = models.IntegerField()

    class Meta:
        unique_together = ['event', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.event.title} (Position: {self.position})"

class Attendance(models.Model):
    """
    Tracks actual attendance/check-in for events.
    Created when organizer marks a registered user as present.
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendance_records')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='attendance', null=True, blank=True)
    checked_in_at = models.DateTimeField(auto_now_add=True)
    checked_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='marked_attendance')
    notes = models.TextField(blank=True)
    is_verified = models.BooleanField(default=True, help_text="Whether attendance has been verified by organizer/admin")

    class Meta:
        unique_together = ['event', 'user']
        verbose_name_plural = 'Attendances'

    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.checked_in_at})"

class Feedback(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField()  # 1-5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['event', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.rating} stars)"

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('event_reminder', 'Event Reminder'),
        ('registration_confirmation', 'Registration Confirmation'),
        ('waitlist_promotion', 'Waitlist Promotion'),
        ('event_cancelled', 'Event Cancelled'),
        ('event_updated', 'Event Updated'),
        ('university_event', 'University Event Alert'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    target_university = models.ForeignKey(University, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.title}"

class RecentActivity(models.Model):
    ACTION_CHOICES = (
        ('registered', 'Registered'),
        ('cancelled', 'Cancelled'),
        ('waitlisted', 'Joined Waitlist'),
        ('promoted', 'Promoted from Waitlist'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recent_activities')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='recent_activities')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Recent Activities'
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.event.title}"