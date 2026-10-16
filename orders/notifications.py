from django.urls import reverse

from accounts.models import User
from accounts.roles import ROLE_DIRECTOR, ROLE_OPERATIONS


def notify_order_created(order, actor):
    """Bell alert for directors, operations, and the people assigned to a new order."""
    number = order.order_no or f'#{order.order_id}'
    client_name = order.client.name if order.client_id else 'A client'
    _alert(
        order,
        actor,
        title=f'Order created: {number}',
        message=f'{client_name} — {order.get_order_type_display()}.',
    )


def notify_order_closed(order, actor):
    """Bell alert when an order is closed."""
    number = order.order_no or f'#{order.order_id}'
    client_name = order.client.name if order.client_id else 'A client'
    _alert(
        order,
        actor,
        title=f'Order closed: {number}',
        message=f'{client_name} is closed.',
    )


def _alert(order, actor, title, message):
    from employee_requests.models import PortalNotification

    recipients = _recipients(order, actor)
    if not recipients:
        return
    link = reverse('order_detail', kwargs={'pk': order.pk})
    PortalNotification.objects.bulk_create([
        PortalNotification(
            user=user,
            title=title,
            message=message,
            link=link,
        )
        for user in recipients
    ])


def _recipients(order, actor):
    """Directors and operations, plus whoever is assigned. Skip the person who did it."""
    user_ids = set(
        User.objects.filter(
            is_active=True,
            role__in=(ROLE_DIRECTOR, ROLE_OPERATIONS),
        ).values_list('pk', flat=True)
    )
    for user_id in (
        order.assigned_project_manager_id,
        order.assigned_supervisor_id,
        order.assigned_to_id,
        order.created_by_id,
    ):
        if user_id:
            user_ids.add(user_id)
    actor_id = getattr(actor, 'pk', None)
    if actor_id:
        user_ids.discard(actor_id)
    if not user_ids:
        return []
    return list(User.objects.filter(pk__in=user_ids, is_active=True))
