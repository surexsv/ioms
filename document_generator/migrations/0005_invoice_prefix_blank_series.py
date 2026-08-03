from django.db import migrations, models


def clear_invoice_prefix(apps, schema_editor):
    DocumentNumberSettings = apps.get_model('document_generator', 'DocumentNumberSettings')
    DocumentNumberSettings.objects.filter(pk=1).update(invoice_prefix='')


def restore_invoice_prefix(apps, schema_editor):
    DocumentNumberSettings = apps.get_model('document_generator', 'DocumentNumberSettings')
    DocumentNumberSettings.objects.filter(pk=1).update(invoice_prefix='INV')


class Migration(migrations.Migration):

    dependencies = [
        ('document_generator', '0004_documentnumbersettings_request_prefix_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='documentnumbersettings',
            name='invoice_prefix',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Leave blank for series like ITSPL26270001 (company + year + serial).',
                max_length=10,
            ),
        ),
        migrations.RunPython(clear_invoice_prefix, restore_invoice_prefix),
    ]
