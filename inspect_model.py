from events.models import University
for f in University._meta.get_fields():
    print(f.name)
