import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendance_date', models.DateField()),
                ('check_in_time', models.TimeField(blank=True, null=True)),
                ('check_out_time', models.TimeField(blank=True, null=True)),
                ('working_hours', models.DecimalField(blank=True, decimal_places=2, help_text='Calculated from check-in and check-out', max_digits=5, null=True)),
                ('location', models.CharField(blank=True, max_length=500)),
                ('latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('status', models.CharField(choices=[('PRESENT', 'Present'), ('ABSENT', 'Absent'), ('HALF_DAY', 'Half Day'), ('LEAVE', 'Leave')], default='PRESENT', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Attendance records',
                'ordering': ['-attendance_date', 'employee'],
            },
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=('employee', 'attendance_date'), name='unique_employee_attendance_date'),
        ),
    ]
