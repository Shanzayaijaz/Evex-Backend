from django.db import migrations, models


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('events', 'UserProfile')

    existing_user_ids = set(
        UserProfile.objects.values_list('user_id', flat=True)
    )

    profiles_to_create = []
    for user in User.objects.exclude(id__in=existing_user_ids):
        profiles_to_create.append(
            UserProfile(
                user_id=user.id,
                user_type='student',
                contact_number='',
                department='',
                student_id=''
            )
        )

    if profiles_to_create:
        UserProfile.objects.bulk_create(profiles_to_create)


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_merge_20251118_0003'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='user',
            field=models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='profile', related_query_name='profile', to='auth.user'),
        ),
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]

