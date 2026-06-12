from django.db import migrations, models


def backfill_pan_from_gstin(apps, schema_editor):
    Client = apps.get_model('clients', 'Client')
    from billing.gst import pan_from_gstin

    for client in Client.objects.exclude(gst_number=''):
        if not (client.pan_number or '').strip():
            pan = pan_from_gstin(client.gst_number)
            if pan:
                client.pan_number = pan
                client.save(update_fields=['pan_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0003_sync_client_gst_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='pan_number',
            field=models.CharField(
                blank=True,
                help_text='10-character PAN; auto-filled from GSTIN when possible',
                max_length=10,
                verbose_name='PAN Number',
            ),
        ),
        migrations.RunPython(backfill_pan_from_gstin, migrations.RunPython.noop),
    ]
