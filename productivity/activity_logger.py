"""Automatic activity logging — call from views/services after key actions."""

from django.utils import timezone

from productivity.constants import ACTIVITY_DEPARTMENT
from productivity.models import EmployeeActivityLog


def log_activity(
    user,
    activity_type,
    *,
    related_document='',
    related_model='',
    related_object_id=None,
    remarks='',
    activity_date=None,
    department=None,
):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    from company_settings.field_ops import is_productivity_enabled
    if not is_productivity_enabled():
        return None
    dept = department or ACTIVITY_DEPARTMENT.get(activity_type, 'OPERATIONS')
    return EmployeeActivityLog.objects.create(
        activity_date=activity_date or timezone.localdate(),
        employee=user,
        department=dept,
        activity_type=activity_type,
        related_document=related_document[:120],
        related_model=related_model[:50],
        related_object_id=related_object_id,
        remarks=remarks,
    )
