import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('clients', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('module', models.CharField(choices=[('ENQUIRY', 'Enquiry'), ('ESTIMATE_BOQ', 'Estimate BOQ'), ('QUOTATION', 'Quotation'), ('ORDER', 'Order'), ('SCHEDULE', 'Schedule'), ('WCR', 'WCR'), ('INVOICE', 'Invoice'), ('PAYMENT', 'Payment'), ('BOQ', 'BOQ')], db_index=True, max_length=20)),
                ('document_type', models.CharField(db_index=True, max_length=30)),
                ('document_number', models.CharField(db_index=True, max_length=60)),
                ('description', models.CharField(max_length=200)),
                ('previous_status', models.CharField(blank=True, max_length=50)),
                ('new_status', models.CharField(blank=True, max_length=50)),
                ('user_role', models.CharField(blank=True, max_length=30)),
                ('remarks', models.TextField(blank=True)),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='case_activities', to='clients.client')),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='case_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-activity_at'],
            },
        ),
        migrations.AddIndex(
            model_name='caseactivitylog',
            index=models.Index(fields=['module', 'object_id'], name='case_intell_module_4a8f2d_idx'),
        ),
        migrations.AddIndex(
            model_name='caseactivitylog',
            index=models.Index(fields=['document_number'], name='case_intell_documen_8c3e1a_idx'),
        ),
        migrations.AddIndex(
            model_name='caseactivitylog',
            index=models.Index(fields=['client', '-activity_at'], name='case_intell_client__9d2f4b_idx'),
        ),
        migrations.AddIndex(
            model_name='caseactivitylog',
            index=models.Index(fields=['-activity_at', 'module'], name='case_intell_activit_1e7c3d_idx'),
        ),
    ]
