from django.db import migrations


def sync_clients(apps, schema_editor):
    Client = apps.get_model('clients', 'Client')
    from billing.gst import sync_client_gst_fields

    for client in Client.objects.all():
        sync_client_gst_fields(client, save=True)


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0002_alter_client_options_client_gst_type_client_state_and_more'),
    ]

    operations = [
        migrations.RunPython(sync_clients, migrations.RunPython.noop),
    ]
