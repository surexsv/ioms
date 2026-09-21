from .utils import dashboard_url_name_for_user
from .models import User
from .roles import user_role, is_field_staff, ROLE_SUPERVISOR, LEGACY_SUPERVISOR
from .permissions import (
    can_view_clients,
    can_view_orders,
    can_view_wcr,
    can_view_boq,
    can_manage_billing,
    can_manage_attendance,
    can_view_attendance_audit_data,
    can_view_own_attendance,
    can_view_team_attendance,
    show_nav_my_attendance,
    show_nav_attendance_management,
    show_nav_team_attendance,
    can_view_quotations,
    can_view_financial,
    can_view_company_settings,
    can_manage_user_approvals,
    can_access,
    MODULE_SCHEDULING,
    MODULE_CASE_INTELLIGENCE,
    MODULE_ERMS,
    MODULE_PREVENTIVE_MAINTENANCE,
    MODULE_ERMS_APPROVE,
    has_full_access,
    attendance_nav_url,
)
from .enterprise_permissions import build_navigation_menu, dashboard_widget_flags
from employee_requests.permissions import can_access_erms, can_approve_requests
from daily_meetings.permissions import can_access_daily_meetings
from productivity.permissions import (
    can_view_gps_dashboard,
    can_view_management_productivity,
)


def _active_nav(request):
    path = request.path
    if path.startswith('/dashboard'):
        return 'dashboard'
    if path.startswith('/enquiries'):
        return 'enquiries'
    if path.startswith('/orders'):
        return 'orders'
    if path.startswith('/clients'):
        return 'clients'
    if path.startswith('/quotations'):
        return 'quotations'
    if path.startswith('/wcr'):
        return 'wcr'
    if path.startswith('/boq'):
        return 'boq'
    if path.startswith('/billing'):
        return 'billing'
    if path.startswith('/attendance'):
        return 'attendance'
    if path.startswith('/document-generator'):
        return 'document_numbers'
    if path.startswith('/company-settings'):
        return 'company_settings'
    if path.startswith('/scheduling'):
        return 'schedules'
    if path.startswith('/special-projects'):
        return 'special_projects'
    if path.startswith('/fleet'):
        return 'fleet'
    if path.startswith('/project-expenses'):
        return 'project_expenses'
    if path.startswith('/preventive-maintenance'):
        return 'preventive_maintenance'
    if path.startswith('/case-intelligence/reports'):
        return 'reports'
    if path.startswith('/case-intelligence'):
        return 'case_intelligence'
    if path.startswith('/daily-meetings'):
        return 'daily_meetings'
    if path.startswith('/requests'):
        return 'employee_requests'
    if path.startswith('/productivity/gps'):
        return 'gps'
    if path.startswith('/productivity'):
        return 'productivity'
    if path.startswith('/user-approvals'):
        return 'user_approvals'
    return ''


def _nav_keys_from_sections(sections):
    keys = set()
    for section in sections:
        for item in section.get('items', []):
            keys.add(item.get('nav_key'))
    return keys


def _show_pm_nav(user, nav_keys):
    if 'preventive_maintenance' in nav_keys:
        return True
    from preventive_maintenance.permissions import can_view_pm
    return can_view_pm(user)


def oms_navigation(request):
    user = request.user
    if not user.is_authenticated:
        return {}
    if not getattr(user, 'is_profile_approved', True):
        return {}
    role = user_role(user)
    raw_role = getattr(user, 'role', None)
    dashboard_url = dashboard_url_name_for_user(user)
    enterprise_nav_sections = build_navigation_menu(user, dashboard_url)
    nav_keys = _nav_keys_from_sections(enterprise_nav_sections)
    widget_flags = dashboard_widget_flags(user)

    pending_approval_count = 0
    if can_manage_user_approvals(user):
        pending_approval_count = User.objects.filter(
            approval_status=User.APPROVAL_PENDING,
        ).exclude(is_superuser=True).count()
    erms_notification_count = 0
    if can_access_erms(user):
        from employee_requests.models import PortalNotification
        erms_notification_count = PortalNotification.objects.filter(
            user=user, is_read=False,
        ).count()
    return {
        'dashboard_url': dashboard_url,
        'enterprise_nav_sections': enterprise_nav_sections,
        'nav_active': _active_nav(request),
        'is_superuser': has_full_access(user),
        'user_role': raw_role,
        'user_role_display': user.get_role_display() if hasattr(user, 'get_role_display') else raw_role,
        'show_nav_dashboard': (
            'dashboard' in nav_keys
            or (bool(dashboard_url) and dashboard_url != 'login')
        ),
        'show_nav_enquiries': False,
        'show_nav_orders': 'orders' in nav_keys or can_view_orders(user),
        'show_nav_clients': 'clients' in nav_keys or can_view_clients(user),
        'show_nav_quotations': 'quotations' in nav_keys or can_view_quotations(user),
        'show_nav_wcr': 'wcr' in nav_keys or can_view_wcr(user),
        'show_nav_boq': 'boq' in nav_keys or can_view_boq(user),
        'show_nav_billing': 'billing' in nav_keys or can_manage_billing(user),
        'show_nav_my_attendance': 'attendance' in nav_keys or show_nav_my_attendance(user),
        'show_nav_attendance_management': 'attendance_mgmt' in nav_keys or show_nav_attendance_management(user),
        'show_nav_team_attendance': 'attendance_team' in nav_keys or show_nav_team_attendance(user),
        'show_nav_attendance': (
            'attendance' in nav_keys
            or 'attendance_mgmt' in nav_keys
            or 'attendance_team' in nav_keys
            or show_nav_my_attendance(user)
            or show_nav_attendance_management(user)
            or show_nav_team_attendance(user)
        ),
        'attendance_nav_url': attendance_nav_url(user),
        'attendance_required': show_nav_my_attendance(user),
        'is_field_staff': is_field_staff(raw_role),
        'can_view_financial': can_view_financial(user),
        'is_management': can_view_clients(user) and role in ('DIRECTOR', 'OPERATIONS', 'PROJECT_MANAGER'),
        'is_supervisor': role == ROLE_SUPERVISOR or raw_role == LEGACY_SUPERVISOR,
        'is_management_attendance': can_manage_attendance(user),
        'can_view_team_attendance': can_view_team_attendance(user),
        'can_view_attendance_audit_data': can_view_attendance_audit_data(user),
        'can_check_in': show_nav_my_attendance(user),
        'can_view_quotations': can_view_quotations(user),
        'show_nav_document_numbers': 'document_numbers' in nav_keys,
        'show_nav_company_settings': 'company_settings' in nav_keys or can_view_company_settings(user),
        'show_nav_user_approvals': 'user_approvals' in nav_keys or can_manage_user_approvals(user),
        'show_nav_productivity': 'productivity' in nav_keys or can_view_management_productivity(user),
        'show_nav_gps': 'gps' in nav_keys or can_view_gps_dashboard(user),
        'show_nav_schedules': 'schedules' in nav_keys or can_access(user, MODULE_SCHEDULING),
        'show_nav_case_intelligence': (
            'case_intelligence' in nav_keys or 'reports' in nav_keys
            or can_access(user, MODULE_CASE_INTELLIGENCE)
        ),
        'show_nav_daily_meetings': 'daily_meetings' in nav_keys or can_access_daily_meetings(user),
        'show_nav_employee_requests': 'employee_requests' in nav_keys or can_access_erms(user),
        'show_nav_erms_pending': can_approve_requests(user),
        'erms_notification_count': erms_notification_count,
        'pending_approval_count': pending_approval_count,
        **widget_flags,
        # Keep after widget_flags so a dashboard flag cannot hide the sidebar item.
        'show_nav_preventive_maintenance': _show_pm_nav(user, nav_keys),
    }
