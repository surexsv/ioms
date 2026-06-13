from django.db import migrations, models


def copy_legacy_thresholds(apps, schema_editor):
    CaseIntelligenceSettings = apps.get_model('company_settings', 'CaseIntelligenceSettings')
    for obj in CaseIntelligenceSettings.objects.all():
        obj.enquiry_delay_days = obj.enquiry_inactive_days
        obj.order_delay_days = obj.order_schedule_delay_days
        obj.wcr_delay_days = obj.wcr_submit_delay_days
        obj.save(update_fields=[
            'enquiry_delay_days', 'order_delay_days', 'wcr_delay_days',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0006_caseintelligencesettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseintelligencesettings',
            name='enquiry_delay_days',
            field=models.PositiveSmallIntegerField(default=7, verbose_name='Enquiry delay days'),
        ),
        migrations.AddField(
            model_name='caseintelligencesettings',
            name='survey_delay_days',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Survey delay days'),
        ),
        migrations.AddField(
            model_name='caseintelligencesettings',
            name='order_delay_days',
            field=models.PositiveSmallIntegerField(default=5, verbose_name='Order delay days'),
        ),
        migrations.AddField(
            model_name='caseintelligencesettings',
            name='wcr_delay_days',
            field=models.PositiveSmallIntegerField(default=3, verbose_name='WCR delay days'),
        ),
        migrations.AddField(
            model_name='caseintelligencesettings',
            name='invoice_approval_days',
            field=models.PositiveSmallIntegerField(default=3, verbose_name='Invoice approval days'),
        ),
        migrations.AddField(
            model_name='caseintelligencesettings',
            name='payment_followup_days',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Payment follow-up days'),
        ),
        migrations.RunPython(copy_legacy_thresholds, migrations.RunPython.noop),
    ]
