from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


SOURCE_MAP = {
    'PHONE': 'PHONE',
    'EMAIL': 'EMAIL',
    'WEBSITE': 'WEBSITE',
    'REFERRAL': 'REFERRAL',
    'WALK_IN': 'WALK_IN',
    'EXISTING_CLIENT': 'EXISTING_CUSTOMER',
    'OTHER': 'INTERNAL',
}

TYPE_MAP = {
    'SURVEY': 'SURVEY',
    'INSTALLATION': 'INSTALLATION',
    'COMPLAINT': 'COMPLAINT',
    'MAINTENANCE': 'MAINTENANCE',
    'AMC': 'AMC_VISIT',
    'UPGRADE': 'UPGRADE',
}


def migrate_enquiry_data_to_orders(apps, schema_editor):
    Enquiry = apps.get_model('enquiries', 'Enquiry')
    Order = apps.get_model('orders', 'Order')

    for enquiry in Enquiry.objects.filter(converted_order_id__isnull=False).iterator():
        order = Order.objects.filter(pk=enquiry.converted_order_id).first()
        if not order:
            continue
        changed = False
        if not order.source and enquiry.source:
            order.source = SOURCE_MAP.get(enquiry.source, 'INTERNAL')
            changed = True
        if enquiry.contact_person and not order.contact_person:
            order.contact_person = enquiry.contact_person
            changed = True
        if enquiry.mobile and not order.mobile:
            order.mobile = enquiry.mobile
            changed = True
        if enquiry.email and not order.email:
            order.email = enquiry.email
            changed = True
        if enquiry.assigned_project_manager_id and not order.assigned_project_manager_id:
            order.assigned_project_manager_id = enquiry.assigned_project_manager_id
            changed = True
        if enquiry.assigned_supervisor_id and not order.assigned_supervisor_id:
            order.assigned_supervisor_id = enquiry.assigned_supervisor_id
            changed = True
        if enquiry.created_by_id and not order.created_by_id:
            order.created_by_id = enquiry.created_by_id
            changed = True
        if enquiry.enquiry_type and order.order_type in ('SURVEY', 'INSTALLATION', 'COMPLAINT', 'MAINTENANCE'):
            mapped = TYPE_MAP.get(enquiry.enquiry_type)
            if mapped:
                order.order_type = mapped
                changed = True
        if changed:
            order.save()


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_order_expected_completion_date_order_order_date_and_more'),
        ('enquiries', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='order_type',
            field=models.CharField(
                choices=[
                    ('SURVEY', 'Survey'),
                    ('INSTALLATION', 'Installation'),
                    ('COMPLAINT', 'Complaint'),
                    ('MAINTENANCE', 'Maintenance'),
                    ('AMC_VISIT', 'AMC Visit'),
                    ('PREVENTIVE_MAINTENANCE', 'Preventive Maintenance'),
                    ('SHIFTING', 'Shifting'),
                    ('UPGRADE', 'Upgrade'),
                    ('INTERNAL', 'Internal Work'),
                    ('OTHER', 'Other'),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='source',
            field=models.CharField(
                blank=True,
                choices=[
                    ('PHONE', 'Phone Call'),
                    ('WHATSAPP', 'WhatsApp'),
                    ('EMAIL', 'Email'),
                    ('WEBSITE', 'Website'),
                    ('EXISTING_CUSTOMER', 'Existing Customer'),
                    ('TENDER', 'Tender'),
                    ('REFERRAL', 'Referral'),
                    ('WALK_IN', 'Walk-in'),
                    ('INTERNAL', 'Internal'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='contact_person',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='order',
            name='mobile',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='order',
            name='assigned_project_manager',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='orders_as_pm',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='assigned_supervisor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='orders_as_supervisor',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='orders_created',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(migrate_enquiry_data_to_orders, migrations.RunPython.noop),
    ]
