# Generated manually for ERMS initial schema

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RequestType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codename', models.CharField(db_index=True, max_length=30, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('requires_amount', models.BooleanField(default=False)),
                ('approver_role_hints', models.CharField(blank=True, help_text='Comma-separated role codenames suggested for Submitted To dropdown.', max_length=200)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('approval_chain_config', models.JSONField(blank=True, default=dict)),
                ('notification_config', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='EmployeeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_number', models.CharField(blank=True, db_index=True, max_length=30, unique=True)),
                ('request_date', models.DateField(db_index=True, default=django.utils.timezone.localdate)),
                ('department', models.CharField(blank=True, max_length=100)),
                ('priority', models.CharField(choices=[('LOW', 'Low'), ('NORMAL', 'Normal'), ('HIGH', 'High'), ('URGENT', 'Urgent')], default='NORMAL', max_length=10)),
                ('subject', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('UNDER_REVIEW', 'Under Review'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('RETURNED', 'Returned for Correction'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')], db_index=True, default='DRAFT', max_length=20)),
                ('remarks', models.TextField(blank=True)),
                ('sla_due_at', models.DateTimeField(blank=True, null=True)),
                ('approval_step', models.PositiveSmallIntegerField(default=1)),
                ('escalation_level', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('request_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='employee_requests.requesttype')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='employee_requests_created', to=settings.AUTH_USER_MODEL)),
                ('submitted_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='employee_requests_inbox', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-request_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RequestApprovalHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(db_index=True, max_length=40)),
                ('from_status', models.CharField(blank=True, max_length=20)),
                ('to_status', models.CharField(blank=True, max_length=20)),
                ('remarks', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('channel', models.CharField(blank=True, default='portal', max_length=20)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='request_approval_actions', to=settings.AUTH_USER_MODEL)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approval_history', to='employee_requests.employeerequest')),
            ],
            options={
                'verbose_name_plural': 'Request approval history',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='RequestAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='employee_requests/%Y/%m/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx'])])),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='employee_requests.employeerequest')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='PortalNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField(blank=True)),
                ('link', models.CharField(blank=True, max_length=300)),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('email_sent_at', models.DateTimeField(blank=True, null=True)),
                ('whatsapp_sent_at', models.DateTimeField(blank=True, null=True)),
                ('related_request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='employee_requests.employeerequest')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='portal_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
