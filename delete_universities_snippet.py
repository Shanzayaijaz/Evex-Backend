from events.models import University, Event, Venue
from django.db.models import Q

def delete_universities():
    target_names = ["Uni A", "Uni Delete", "Race Test Uni"]
    
    for name in target_names:
        print(f"\nProcessing deletion for: {name}")
        # Find university (case insensitive)
        universities = University.objects.filter(name__icontains=name)
        
        if not universities.exists():
            print(f"No university found matching '{name}'")
            continue
            
        for uni in universities:
            print(f"Found University: {uni.name} (ID: {uni.id})")
            
            # 1. Find all venues for this university
            venues = Venue.objects.filter(university=uni)
            print(f"- Found {venues.count()} venues")
            
            # 2. Find all events using these venues (these cause the ProtectedError)
            events_at_venues = Event.objects.filter(venue__in=venues)
            event_count = events_at_venues.count()
            print(f"- Found {event_count} events using these venues")
            
            if event_count > 0:
                print("  Deleting events...")
                # We can use delete() directly on the queryset
                # Note: This might trigger soft delete if we were using the viewset, 
                # but here we are using the model directly so it's a hard delete.
                # Given the user wants to clean up, hard delete is appropriate here.
                events_at_venues.delete()
                print("  Events deleted.")
            
            # 3. Delete the university (will cascade delete venues)
            print(f"Deleting University: {uni.name}")
            uni.delete()
            print("University deleted.")

if __name__ == '__main__':
    delete_universities()
