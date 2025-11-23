from django.db import migrations


def deactivate_fast_nu(apps, schema_editor):
    University = apps.get_model('events', 'University')
    University.objects.filter(name__iexact='FAST-NU Karachi').update(is_active=False)


def reactivate_fast_nu(apps, schema_editor):
    University = apps.get_model('events', 'University')
    University.objects.filter(name__iexact='FAST-NU Karachi').update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_event_image'),
    ]

    operations = [
        migrations.RunPython(deactivate_fast_nu, reactivate_fast_nu),
    ]

