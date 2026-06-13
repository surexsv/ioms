import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='check_in_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_out_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_in_maps_link',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_out_location',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_out_latitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_out_longitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_out_maps_link',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='attendance',
            name='device_info_in',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='attendance',
            name='device_info_out',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='attendance',
            name='ip_address_in',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='ip_address_out',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_in_remarks',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='check_out_remarks',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='is_corrected',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='attendance',
            name='corrected_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendance_corrections',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='attendance',
            name='attendance_date',
            field=models.DateField(db_index=True),
        ),
        migrations.AlterField(
            model_name='attendance',
            name='location',
            field=models.CharField(blank=True, help_text='Check-in address', max_length=500),
        ),
        migrations.AlterField(
            model_name='attendance',
            name='status',
            field=models.CharField(
                choices=[
                    ('PRESENT', 'Present'),
                    ('ABSENT', 'Absent'),
                    ('HALF_DAY', 'Half Day'),
                    ('LEAVE', 'Leave'),
                    ('LATE', 'Late Arrival'),
                ],
                db_index=True,
                default='PRESENT',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['employee', '-attendance_date'], name='attendance_employe_6a8f0d_idx'),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['attendance_date', 'status'], name='attendance_attenda_8b2c1a_idx'),
        ),
        migrations.CreateModel(
            name='AttendancePhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo_type', models.CharField(
                    choices=[('CHECK_IN', 'Check-In Photo'), ('CHECK_OUT', 'Check-Out Photo')],
                    db_index=True, max_length=12,
                )),
                ('image', models.ImageField(upload_to='attendance_photos/%Y/%m/')),
                ('captured_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('attendance', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='photos',
                    to='attendance.attendance',
                )),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_photos',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-captured_at']},
        ),
        migrations.CreateModel(
            name='AttendanceAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(db_index=True, max_length=40)),
                ('user_role', models.CharField(blank=True, max_length=30)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('device_info', models.CharField(blank=True, max_length=500)),
                ('latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('remarks', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('attendance', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs',
                    to='attendance.attendance',
                )),
                ('performed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='attendance_audit_actions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
