from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from events.models import UserProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Fixes user roles for organizers who were incorrectly assigned as students'

    def handle(self, *args, **kwargs):
        self.stdout.write('Scanning for organizers with incorrect roles...')
        
        # Find users with 'organizer' in their email or username who are currently marked as students
        potential_organizers = User.objects.filter(
            profile__user_type='student'
        ).filter(
            email__icontains='organizer'
        ) | User.objects.filter(
            profile__user_type='student'
        ).filter(
            username__icontains='organizer'
        )
        
        count = 0
        for user in potential_organizers:
            profile = user.profile
            profile.user_type = 'organizer'
            profile.save()
            self.stdout.write(f'Updated role for: {user.email}')
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {count} organizer roles'))
