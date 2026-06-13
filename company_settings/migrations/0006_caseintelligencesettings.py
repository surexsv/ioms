import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0005_fieldoperationssettings'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseIntelligenceSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enquiry_inactive_days', models.PositiveSmallIntegerField(default=7)),
                ('quotation_followup_days', models.PositiveSmallIntegerField(default=15)),
                ('order_schedule_delay_days', models.PositiveSmallIntegerField(default=5)),
                ('wcr_submit_delay_days', models.PositiveSmallIntegerField(default=3)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='case_intel_settings_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Case intelligence settings',
                'verbose_name_plural': 'Case intelligence settings',
            },
        ),
    ]
