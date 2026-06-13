from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_intelligence', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseactivitylog',
            name='backfill_key',
            field=models.CharField(
                blank=True, db_index=True, max_length=120, null=True, unique=True,
                help_text='Idempotency key for historical backfill — not set for live events.',
            ),
        ),
    ]
