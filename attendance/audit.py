"""Attendance audit trail."""

from accounts.roles import user_role
from attendance.models import AttendanceAuditLog


def log_attendance_event(
    action,
    *,
    attendance=None,
    user=None,
    request=None,
    remarks='',
    latitude=None,
    longitude=None,
):
    ip = ''
    device = ''
    if request:
        from attendance.utils import get_client_ip, get_device_info
        ip = get_client_ip(request)
        device = get_device_info(request)
    AttendanceAuditLog.objects.create(
        attendance=attendance,
        action=action,
        performed_by=user if user and user.is_authenticated else None,
        user_role=user_role(user) if user and user.is_authenticated else '',
        ip_address=ip or None,
        device_info=device,
        latitude=latitude,
        longitude=longitude,
        remarks=remarks,
    )
