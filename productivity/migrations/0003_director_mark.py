from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('productivity', '0002_gpslocationrecord_fieldactivitylog_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeproductivitysnapshot',
            name='director_mark',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Director mark from 0 to 100. Counts as 10% of the monthly score.',
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='employeeproductivitysnapshot',
            name='director_mark_note',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='employeeproductivitysnapshot',
            name='director_marked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='employeeproductivitysnapshot',
            name='director_marked_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='director_marks_entered',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
