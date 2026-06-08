from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def migrate_order_scheduling_data(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    WorkSchedule = apps.get_model('scheduling', 'WorkSchedule')
    User = apps.get_model('accounts', 'User')

    status_map = {
        'NEW': 'PLANNED',
        'SCHEDULED': 'ASSIGNED',
        'IN_PROGRESS': 'IN_PROGRESS',
        'COMPLETED': 'COMPLETED',
    }

    for order in Order.objects.all():
        if order.target_date and not order.expected_completion_date:
            order.expected_completion_date = order.target_date
            order.save(update_fields=['expected_completion_date'])

        if WorkSchedule.objects.filter(order_id=order.pk).exists():
            continue

        has_assignment = bool(order.assigned_to_id)
        is_scheduled_status = order.status in ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED')
        if not has_assignment and not is_scheduled_status:
            continue

        start = order.order_date or timezone.now().date()
        end = order.expected_completion_date or order.target_date or start
        if end < start:
            end = start

        schedule_status = status_map.get(order.status, 'PLANNED')
        if has_assignment and schedule_status == 'PLANNED':
            schedule_status = 'ASSIGNED'

        try:
            from document_generator.constants import DOC_SCHEDULE
            from document_generator.services import generate_document_number
            schedule_number = generate_document_number(DOC_SCHEDULE)
        except Exception:
            schedule_number = f'MIG-{order.order_no or order.order_id}'

        schedule = WorkSchedule.objects.create(
            order_id=order.pk,
            schedule_number=schedule_number,
            scheduled_start_date=start,
            scheduled_end_date=end,
            status=schedule_status,
        )

        if order.assigned_to_id:
            through = WorkSchedule.assigned_engineers.through
            through.objects.get_or_create(
                workschedule_id=schedule.pk,
                user_id=order.assigned_to_id,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0001_initial'),
        ('orders', '0003_order_expected_completion_date_order_order_date_and_more'),
        ('document_generator', '0002_documentnumbersettings_schedule_prefix_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_order_scheduling_data, migrations.RunPython.noop),
    ]
