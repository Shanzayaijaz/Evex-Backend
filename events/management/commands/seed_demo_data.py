from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from events.models import (
    University,
    EventCategory,
    Venue,
    Event,
    UserProfile,
    Registration,
)


class Command(BaseCommand):
    help = "Seeds demo universities, venues, users, and events for local testing."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting demo data seeding..."))
        with transaction.atomic():
            self._seed_users()
            universities = self._seed_universities()
            categories = self._seed_categories()
            venues = self._seed_venues(universities)
            events = self._seed_events(universities, categories, venues)
            self._seed_registrations(events)
        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))

    def _seed_users(self):
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "first_name": "System",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("123")
            admin_user.save()
        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={
                "user_type": "admin",
                "is_verified": True,
            },
        )

        organizer_user, created = User.objects.get_or_create(
            username="organizer",
            defaults={
                "email": "organizer@example.com",
                "first_name": "Event",
                "last_name": "Manager",
                "is_staff": True,
            },
        )
        if created:
            organizer_user.set_password("123")
            organizer_user.save()

        student_user, created = User.objects.get_or_create(
            username="student",
            defaults={
                "email": "student@example.com",
                "first_name": "Sample",
                "last_name": "Student",
            },
        )
        if created:
            student_user.set_password("123")
            student_user.save()

        # Profiles will be linked to actual universities later
        UserProfile.objects.get_or_create(
            user=organizer_user,
            defaults={
                "user_type": "organizer",
                "is_verified": True,
            },
        )
        UserProfile.objects.get_or_create(
            user=student_user,
            defaults={
                "user_type": "student",
                "is_verified": True,
            },
        )

    def _seed_universities(self):
        universities_data = [
            ("LUMS", "LUMS", "lums.edu.pk"),
            ("IBA Karachi", "IBA", "iba.edu.pk"),
            ("NUST Islamabad", "NUST", "nust.edu.pk"),
            ("Habib University", "HABIB", "habib.edu.pk"),
        ]
        universities = {}
        for name, short_code, domain in universities_data:
            uni, _ = University.objects.get_or_create(
                name=name,
                defaults={
                    "short_code": short_code,
                    "domain": domain,
                    "is_active": True,
                },
            )
            universities[short_code] = uni
        return universities

    def _seed_categories(self):
        categories = {}
        for cat_name, desc in [
            ("Technology", "Hackathons, coding competitions, and tech talks"),
            ("Business", "Summits, entrepreneurship, and corporate events"),
            ("Career", "Career fairs and networking"),
            ("Cultural", "Festivals, concerts, and cultural nights"),
        ]:
            category, _ = EventCategory.objects.get_or_create(
                name=cat_name,
                defaults={"description": desc},
            )
            categories[cat_name] = category
        return categories

    def _seed_venues(self, universities):
        venues = {}
        venue_data = [
            ("LUMS Innovation Lab", "LUMS", 320),
            ("LUMS Main Hall", "LUMS", 400),
            ("IBA City Campus", "IBA", 500),
            ("NUST Convention Center", "NUST", 350),
            ("Habib Amphitheatre", "HABIB", 250),
        ]
        for name, uni_code, capacity in venue_data:
            venue, _ = Venue.objects.get_or_create(
                name=name,
                university=universities[uni_code],
                defaults={
                    "capacity": capacity,
                    "features": {"wifi": True, "projector": True},
                    "is_active": True,
                },
            )
            venues[name] = venue

        # Attach organizer/student profiles to primary university
        organizer_profile = UserProfile.objects.get(user__username="organizer")
        student_profile = UserProfile.objects.get(user__username="student")
        organizer_profile.university = universities["LUMS"]
        organizer_profile.department = "Computer Science"
        organizer_profile.save()

        student_profile.university = universities["LUMS"]
        student_profile.department = "Software Engineering"
        student_profile.save()

        return venues

    def _seed_events(self, universities, categories, venues):
        organizer = User.objects.get(username="organizer")
        now = timezone.now()
        events_seed = [
            {
                "title": "Inter-University Hackathon",
                "description": "48-hour hackathon focused on AI for sustainability.",
                "days_from_now": 10,
                "venue": "LUMS Innovation Lab",
                "university": "LUMS",
                "category": "Technology",
                "participant_limit": 200,
                "visibility": "inter_university",
                "allowed_universities": ["NUST", "IBA"],
            },
            {
                "title": "LUMS Business Summit",
                "description": "Keynotes, workshops, and competitions with industry experts.",
                "days_from_now": 20,
                "venue": "LUMS Main Hall",
                "university": "LUMS",
                "category": "Business",
                "participant_limit": 300,
                "visibility": "public",
                "allowed_universities": [],
            },
            {
                "title": "IBA Career Expo",
                "description": "Meet recruiters from top tech, finance, and consulting firms.",
                "days_from_now": 5,
                "venue": "IBA City Campus",
                "university": "IBA",
                "category": "Career",
                "participant_limit": 400,
                "visibility": "public",
                "allowed_universities": [],
            },
            {
                "title": "NUST Engineering Symposium",
                "description": "A showcase of cutting-edge student engineering projects.",
                "days_from_now": 30,
                "venue": "NUST Convention Center",
                "university": "NUST",
                "category": "Technology",
                "participant_limit": 250,
                "visibility": "inter_university",
                "allowed_universities": ["LUMS", "IBA"],
            },
            {
                "title": "Habib Cultural Festival",
                "description": "Music, art, and cultural performances from across Pakistan.",
                "days_from_now": 40,
                "venue": "Habib Amphitheatre",
                "university": "HABIB",
                "category": "Cultural",
                "participant_limit": 350,
                "visibility": "public",
                "allowed_universities": [],
            },
        ]

        created_events = []
        for data in events_seed:
            event, _ = Event.objects.get_or_create(
                title=data["title"],
                defaults={
                    "description": data["description"],
                    "date_time": now + timedelta(days=data["days_from_now"]),
                    "venue": venues[data["venue"]],
                    "organizer": organizer,
                    "host_university": universities[data["university"]],
                    "category": categories[data["category"]],
                    "participant_limit": data["participant_limit"],
                    "visibility": data["visibility"],
                    "status": "published",
                },
            )
            if data["allowed_universities"]:
                event.allowed_universities.set(
                    [universities[code] for code in data["allowed_universities"]]
                )
            created_events.append(event)

        return created_events

    def _seed_registrations(self, events):
        student = User.objects.get(username="student")
        for event in events[:3]:
            Registration.objects.get_or_create(
                event=event,
                user=student,
                defaults={"status": "registered"},
            )

