"""Sync order status and legacy assignment fields from work schedules."""


def sync_order_from_schedule(schedule):
    from .models import WorkSchedule

    order = schedule.order
    update_fields = []

    primary = schedule.assigned_engineers.first()
    if order.assigned_to_id != (primary.pk if primary else None):
        order.assigned_to = primary
        update_fields.append('assigned_to')

    if schedule.status == WorkSchedule.STATUS_CANCELLED:
        if update_fields:
            order.save(update_fields=update_fields)
        return

    if schedule.status == WorkSchedule.STATUS_COMPLETED:
        if order.status in ('NEW', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED'):
            order.status = 'COMPLETED'
            update_fields.append('status')
    elif schedule.status == WorkSchedule.STATUS_IN_PROGRESS:
        if order.status in ('NEW', 'SCHEDULED', 'IN_PROGRESS'):
            order.status = 'IN_PROGRESS'
            update_fields.append('status')
    elif schedule.status in (WorkSchedule.STATUS_PLANNED, WorkSchedule.STATUS_ASSIGNED):
        if order.status == 'NEW':
            order.status = 'SCHEDULED'
            update_fields.append('status')

    if update_fields:
        order.save(update_fields=update_fields)
