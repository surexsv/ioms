from django.db import migrations, models


def set_attendance_required_defaults(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    no_roles = {'DIRECTOR'}
    for user in User.objects.all():
        if user.is_superuser:
            user.attendance_required = False
        elif user.role in no_roles:
            user.attendance_required = False
        elif user.is_active and getattr(user, 'is_active_employee', True):
            user.attendance_required = True
        else:
            user.attendance_required = False
        user.save(update_fields=['attendance_required'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_field_ops_rbac'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='attendance_required',
            field=models.BooleanField(
                default=True,
                help_text='When enabled, employee must mark daily attendance with photo and GPS.',
            ),
        ),
        migrations.RunPython(set_attendance_required_defaults, migrations.RunPython.noop),
    ]
