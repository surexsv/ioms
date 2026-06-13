"""Personal attendance widget context for role dashboards."""


def personal_attendance_context(user):
    """Return attendance widget data when user must mark attendance."""
    from attendance.permissions import user_requires_attendance
    from attendance.services import employee_month_stats, today_widget

    if not user_requires_attendance(user):
        return {
            'attendance_required': False,
            'attendance_widget': None,
            'today_attendance': None,
            'attendance_month': None,
        }
    widget = today_widget(user)
    return {
        'attendance_required': True,
        'attendance_widget': widget,
        'today_attendance': widget['record'],
        'attendance_month': employee_month_stats(user),
    }
