from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import timedelta
import random

from events.models import (
    University,
    EventCategory,
    Venue,
    Event,
    UserProfile,
    Registration,
)

# Pakistani first names
PAKISTANI_FIRST_NAMES = [
    'Ahmed', 'Ali', 'Hassan', 'Hussain', 'Muhammad', 'Usman', 'Bilal', 'Zain', 'Hamza', 'Omar',
    'Fatima', 'Ayesha', 'Zainab', 'Maryam', 'Sana', 'Hira', 'Amina', 'Sara', 'Aisha', 'Khadija',
    'Abdullah', 'Ibrahim', 'Yusuf', 'Haris', 'Rayyan', 'Ayan', 'Arham', 'Zayan', 'Ayaan',
    'Aiza', 'Haniya', 'Mariam', 'Zara', 'Alisha', 'Hafsa', 'Iqra', 'Laiba', 'Maham', 'Noor',
    'Fahad', 'Saad', 'Taha', 'Waleed', 'Zeeshan', 'Adnan', 'Asad', 'Faisal', 'Kamran', 'Nadeem',
    'Areeba', 'Dua', 'Hiba', 'Jannat', 'Kainat', 'Mahira', 'Nida', 'Rida', 'Saba', 'Tayyaba',
]

# Pakistani last names
PAKISTANI_LAST_NAMES = [
    'Khan', 'Ahmed', 'Ali', 'Hassan', 'Hussain', 'Malik', 'Sheikh', 'Butt', 'Raza', 'Abbas',
    'Iqbal', 'Rashid', 'Qureshi', 'Shah', 'Baig', 'Mirza', 'Hashmi', 'Rizvi', 'Zaidi', 'Naqvi',
    'Javed', 'Akhtar', 'Siddiqui', 'Ansari', 'Farooq', 'Khalid', 'Tariq', 'Yousuf', 'Zaman', 'Rauf',
]

# Event titles and descriptions
EVENT_TITLES = [
    'Tech Innovation Summit', 'AI & Machine Learning Workshop', 'Startup Pitch Competition',
    'Cybersecurity Conference', 'Data Science Bootcamp', 'Web Development Hackathon',
    'Mobile App Development Workshop', 'Blockchain Technology Seminar', 'Cloud Computing Workshop',
    'Digital Marketing Masterclass', 'UI/UX Design Workshop', 'Software Engineering Symposium',
    'Business Analytics Conference', 'Entrepreneurship Summit', 'Career Development Fair',
    'Networking Mixer', 'Industry Leaders Panel', 'Innovation Challenge', 'Tech Career Expo',
    'Research Symposium', 'Cultural Festival', 'Music Concert', 'Art Exhibition', 'Drama Night',
    'Debate Competition', 'Sports Tournament', 'Food Festival', 'Photography Contest',
    'Literary Festival', 'Film Screening', 'Poetry Recitation', 'Stand-up Comedy Night',
    'Fashion Show', 'Dance Competition', 'Talent Show', 'Science Fair', 'Engineering Expo',
    'Medical Conference', 'Law Symposium', 'Economics Forum', 'Psychology Workshop',
    'Environmental Awareness Campaign', 'Social Impact Summit', 'Women Empowerment Conference',
    'Youth Leadership Program', 'Volunteer Fair', 'Community Service Day', 'Blood Donation Drive',
    'Health Awareness Seminar', 'Mental Health Workshop', 'Fitness Challenge', 'Yoga Session',
    'Cooking Class', 'Language Exchange', 'Book Club Meeting', 'Chess Tournament', 'Gaming Competition',
]

EVENT_DESCRIPTIONS = [
    'Join us for an exciting event featuring industry experts and hands-on workshops.',
    'A comprehensive event covering the latest trends and technologies in the field.',
    'Network with professionals and learn from experienced practitioners.',
    'An interactive session with practical demonstrations and Q&A opportunities.',
    'Explore new opportunities and expand your knowledge in this engaging event.',
    'Connect with peers and discover innovative solutions to common challenges.',
    'Learn from the best in the industry through presentations and workshops.',
    'A unique opportunity to gain insights and build valuable connections.',
    'Experience cutting-edge content and interactive learning sessions.',
    'Join industry leaders for an inspiring and educational experience.',
]

DEPARTMENTS = [
    'Computer Science', 'Software Engineering', 'Electrical Engineering', 'Mechanical Engineering',
    'Business Administration', 'Economics', 'Psychology', 'Mathematics', 'Physics', 'Chemistry',
    'Biology', 'Medicine', 'Law', 'Journalism', 'Fine Arts', 'Architecture', 'Civil Engineering',
    'Management Sciences', 'Finance', 'Marketing', 'Accounting', 'International Relations',
]

VENUE_NAMES = [
    'Main Auditorium', 'Conference Hall', 'Seminar Room', 'Lecture Theater', 'Exhibition Hall',
    'Innovation Lab', 'Student Center', 'Sports Complex', 'Cultural Center', 'Library Hall',
    'Engineering Building', 'Business School', 'Science Block', 'Arts Building', 'Medical Center',
    'Outdoor Amphitheater', 'Multi-Purpose Hall', 'Workshop Room', 'Training Center', 'Event Plaza',
]


class Command(BaseCommand):
    help = "Populates the database with 3000 students, 100 events (some overlapping), and organizers for each event."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing students, events, and organizers before populating',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting large data population..."))
        
        if options['clear']:
            self.stdout.write(self.style.WARNING("Clearing existing data..."))
            self._clear_data()
        
        with transaction.atomic():
            # Get existing universities
            universities = list(University.objects.filter(is_active=True).distinct())
            if not universities:
                self.stdout.write(self.style.ERROR("No active universities found in database!"))
                return
            
            self.stdout.write(self.style.SUCCESS(f"Found {len(universities)} active universities"))
            
            # Ensure categories exist
            categories = self._ensure_categories()
            
            # Ensure venues exist for each university
            venues = self._ensure_venues(universities)
            
            # Create 3000 students
            self.stdout.write(self.style.NOTICE("Creating 3000 students..."))
            students = self._create_students(universities, count=3000)
            self.stdout.write(self.style.SUCCESS(f"Created {len(students)} students"))
            
            # Create 100 events with organizers
            self.stdout.write(self.style.NOTICE("Creating 100 events with organizers..."))
            events = self._create_events_with_organizers(universities, categories, venues, count=100)
            self.stdout.write(self.style.SUCCESS(f"Created {len(events)} events with organizers"))
            
            # Create some registrations
            self.stdout.write(self.style.NOTICE("Creating registrations..."))
            self._create_registrations(students, events)
            self.stdout.write(self.style.SUCCESS("Registrations created"))
        
        self.stdout.write(self.style.SUCCESS("Large data population completed successfully!"))

    def _clear_data(self):
        """Clear existing students, events, and organizers"""
        # Delete events (this will cascade to registrations)
        Event.objects.all().delete()
        
        # Delete organizers (users with organizer profile)
        organizer_profiles = UserProfile.objects.filter(user_type='organizer')
        organizer_users = [profile.user for profile in organizer_profiles]
        User.objects.filter(id__in=[u.id for u in organizer_users]).delete()
        
        # Delete students (users with student profile)
        student_profiles = UserProfile.objects.filter(user_type='student')
        student_users = [profile.user for profile in student_profiles]
        User.objects.filter(id__in=[u.id for u in student_users]).delete()
        
        self.stdout.write(self.style.SUCCESS("Cleared existing data"))

    def _ensure_categories(self):
        """Ensure event categories exist"""
        categories_data = [
            ('Technology', 'Tech events, hackathons, and coding competitions'),
            ('Business', 'Business summits, entrepreneurship, and corporate events'),
            ('Career', 'Career fairs, networking, and professional development'),
            ('Cultural', 'Cultural festivals, concerts, and artistic events'),
            ('Academic', 'Academic conferences, symposiums, and research events'),
            ('Sports', 'Sports tournaments and fitness events'),
            ('Social', 'Social gatherings, community service, and volunteer events'),
        ]
        
        categories = {}
        for name, desc in categories_data:
            category, _ = EventCategory.objects.get_or_create(
                name=name,
                defaults={'description': desc}
            )
            categories[name] = category
        
        return categories

    def _ensure_venues(self, universities):
        """Ensure venues exist for each university"""
        venues = []
        for university in universities:
            # Create 3-5 venues per university
            num_venues = random.randint(3, 5)
            for i in range(num_venues):
                venue_name = f"{random.choice(VENUE_NAMES)} - {university.short_code}"
                capacity = random.choice([100, 150, 200, 250, 300, 400, 500])
                
                venue, _ = Venue.objects.get_or_create(
                    name=venue_name,
                    university=university,
                    defaults={
                        'capacity': capacity,
                        'features': {
                            'wifi': True,
                            'projector': True,
                            'sound_system': True,
                            'air_conditioning': True,
                        },
                        'is_active': True,
                    }
                )
                venues.append(venue)
        
        return venues

    def _create_students(self, universities, count=3000):
        """Create students with Pakistani names"""
        students = []
        batch_size = 100
        
        for i in range(0, count, batch_size):
            batch_students = []
            for j in range(batch_size):
                if i + j >= count:
                    break
                
                first_name = random.choice(PAKISTANI_FIRST_NAMES)
                last_name = random.choice(PAKISTANI_LAST_NAMES)
                username = f"student_{i+j+1:05d}"
                email = f"{username}@{random.choice(universities).domain}"
                
                # Check if user already exists
                if User.objects.filter(username=username).exists():
                    continue
                
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='student123',  # Default password
                    first_name=first_name,
                    last_name=last_name,
                )
                
                university = random.choice(universities)
                student_id = f"{university.short_code}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
                department = random.choice(DEPARTMENTS)
                contact_number = f"03{random.randint(10, 99)}{random.randint(1000000, 9999999)}"
                
                # Use get_or_create to avoid duplicate profile creation
                profile, _ = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'university': university,
                        'user_type': 'student',
                        'student_id': student_id,
                        'department': department,
                        'contact_number': contact_number,
                        'is_verified': random.choice([True, False]),  # Some verified, some not
                    }
                )
                
                batch_students.append(user)
            
            students.extend(batch_students)
            self.stdout.write(f"  Created {len(students)}/{count} students...", ending='\r')
        
        self.stdout.write('')  # New line after progress
        return students

    def _create_events_with_organizers(self, universities, categories, venues, count=100):
        """Create events with dedicated organizers"""
        events = []
        category_list = list(categories.values())
        
        # Create time slots - some will overlap for clash detection
        base_date = timezone.now() + timedelta(days=1)
        time_slots = []
        venue_slots = []  # Track venue for each time slot
        
        # Generate time slots over the next 60 days
        for day in range(60):
            date = base_date + timedelta(days=day)
            # Create 2-3 events per day, some overlapping
            for hour in [9, 11, 14, 16, 18]:
                if random.random() > 0.6:  # 40% chance of event at this time
                    time_slots.append(date.replace(hour=hour, minute=0, second=0, microsecond=0))
                    # Randomly assign venue, but some will overlap
                    venue_slots.append(random.choice(venues))
        
        # Create some overlapping events (same time, same venue) for clash detection
        # About 10% of events should have clashes
        num_clashes = int(count * 0.1)
        clash_indices = random.sample(range(len(time_slots)), min(num_clashes * 2, len(time_slots)))
        
        # Pair up clash indices to create overlapping events
        for i in range(0, len(clash_indices) - 1, 2):
            idx1, idx2 = clash_indices[i], clash_indices[i + 1]
            # Make them at the same time and venue
            time_slots[idx2] = time_slots[idx1]
            venue_slots[idx2] = venue_slots[idx1]
        
        # Shuffle and take first 'count' slots
        combined = list(zip(time_slots, venue_slots))
        random.shuffle(combined)
        combined = combined[:count]
        time_slots, venue_slots = zip(*combined) if combined else ([], [])
        
        for i, (event_time, assigned_venue) in enumerate(zip(time_slots, venue_slots)):
            # Create organizer for this event
            organizer_first = random.choice(PAKISTANI_FIRST_NAMES)
            organizer_last = random.choice(PAKISTANI_LAST_NAMES)
            organizer_username = f"organizer_{i+1:03d}"
            organizer_university = random.choice(universities)
            organizer_email = f"{organizer_username}@{organizer_university.domain}"
            
            # Check if organizer already exists
            organizer_user, created = User.objects.get_or_create(
                username=organizer_username,
                defaults={
                    'email': organizer_email,
                    'first_name': organizer_first,
                    'last_name': organizer_last,
                }
            )
            
            if created:
                organizer_user.set_password('organizer123')
                organizer_user.save()
            
            # Create or update organizer profile
            organizer_profile, _ = UserProfile.objects.get_or_create(
                user=organizer_user,
                defaults={
                    'university': organizer_university,
                    'user_type': 'organizer',
                    'department': random.choice(DEPARTMENTS),
                    'contact_number': f"03{random.randint(10, 99)}{random.randint(1000000, 9999999)}",
                    'is_verified': True,
                }
            )
            
            # Ensure organizer is linked to university
            if not organizer_profile.university:
                organizer_profile.university = organizer_university
                organizer_profile.save()
            
            # Use assigned venue (which may have clashes) or select from organizer's university
            university_venues = [v for v in venues if v.university == organizer_university]
            if not university_venues:
                university_venues = venues
            
            # Use assigned venue if it's from organizer's university, otherwise pick from university venues
            if assigned_venue.university == organizer_university:
                venue = assigned_venue
            else:
                # 70% chance to use assigned venue anyway (for clash testing), 30% to use university venue
                venue = assigned_venue if random.random() > 0.3 else random.choice(university_venues)
            
            # Select category
            category = random.choice(category_list)
            
            # Generate event details
            title = random.choice(EVENT_TITLES)
            description = random.choice(EVENT_DESCRIPTIONS)
            participant_limit = random.choice([50, 100, 150, 200, 250, 300, 400, 500])
            visibility = random.choice(['university', 'inter_university', 'public'])
            
            # Mostly published, some drafts
            status_choice = random.choice(['published', 'published', 'published', 'draft'])
            
            # Create event - try as published first, if it clashes, save as draft
            try:
                event = Event.objects.create(
                    title=f"{title} #{i+1}",
                    description=description,
                    date_time=event_time,
                    venue=venue,
                    organizer=organizer_user,
                    host_university=organizer_university,
                    category=category,
                    participant_limit=participant_limit,
                    visibility=visibility,
                    status=status_choice,
                )
            except DjangoValidationError:
                # If validation fails due to clash, save as draft instead
                event = Event.objects.create(
                    title=f"{title} #{i+1}",
                    description=description,
                    date_time=event_time,
                    venue=venue,
                    organizer=organizer_user,
                    host_university=organizer_university,
                    category=category,
                    participant_limit=participant_limit,
                    visibility=visibility,
                    status='draft',  # Save as draft to avoid clash
                )
            
            # Set allowed universities for inter_university events
            if visibility == 'inter_university' and random.random() > 0.5:
                # Allow 2-4 other universities
                other_universities = [u for u in universities if u != organizer_university]
                num_allowed = min(random.randint(2, 4), len(other_universities))
                allowed = random.sample(other_universities, num_allowed)
                event.allowed_universities.set(allowed)
            
            events.append(event)
            
            if (i + 1) % 10 == 0:
                self.stdout.write(f"  Created {i+1}/{count} events...", ending='\r')
        
        self.stdout.write('')  # New line after progress
        return events

    def _create_registrations(self, students, events):
        """Create some registrations for events"""
        # Register 20-50% of students to random events
        num_registrations = random.randint(int(len(students) * 0.2), int(len(students) * 0.5))
        
        registered_pairs = set()
        created_count = 0
        
        self.stdout.write(f"Attempting to create {num_registrations} registrations...")
        
        for i in range(num_registrations):
            student = random.choice(students)
            event = random.choice(events)
            
            # Avoid duplicate registrations in this run
            pair = (student.id, event.id)
            if pair in registered_pairs:
                continue
            registered_pairs.add(pair)
            
            # Only register for published events
            if event.status != 'published':
                continue
            
            # Check university eligibility
            try:
                student_profile = UserProfile.objects.get(user=student)
                student_university = student_profile.university
                
                if event.visibility == 'university':
                    if student_university != event.host_university:
                        continue
                elif event.visibility == 'inter_university':
                    allowed = event.allowed_universities.all()
                    if allowed.exists() and student_university not in allowed:
                        continue
            except UserProfile.DoesNotExist:
                # Student without profile can only register for public events
                if event.visibility != 'public':
                    continue
            
            # Create registration safely
            # Use get_or_create to avoid race conditions if this script is run multiple times
            _, created = Registration.objects.get_or_create(
                event=event,
                user=student,
                defaults={'status': 'registered'}
            )
            
            if created:
                created_count += 1
                
            if (i + 1) % 100 == 0:
                self.stdout.write(f"  Processed {i+1}/{num_registrations} registration attempts...", ending='\r')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f"Successfully created {created_count} new registrations"))

