from django.db import migrations


def migrate_supervisor_role(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='Supervisor').update(role='SUPERVISOR')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_reports_to_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(migrate_supervisor_role, migrations.RunPython.noop),
    ]
