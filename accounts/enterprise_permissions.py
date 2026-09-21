"""Enterprise permission resolution — Phase 2.

Access control uses individual Employee permission grants.
Legacy role/_ACCESS is fallback only when no employee profile exists.
"""

from django.core.cache import cache

from accounts.enterprise_constants import LEGACY_MODULE_TO_PERMISSION, SUPERUSER_ONLY_PERMISSIONS

_CACHE_KEY = 'ioms_enterprise_perms_v1'
_CACHE_TTL = 300


def invalidate_enterprise_permission_cache(user_id=None):
    if user_id:
        cache.delete(f'{_CACHE_KEY}:{user_id}')
    else:
        cache.delete_many([])  # pattern delete not available; clear known users lazily


def _cache_key(user):
    return f'{_CACHE_KEY}:{user.pk}'


def get_employee_profile(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.employee_profile
    except Exception:
        return None


def has_employee_profile(user):
    return get_employee_profile(user) is not None


def get_user_permission_codenames(user):
    """Active module permission codenames for this user."""
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        from accounts.enterprise_models import ModulePermission
        return set(ModulePermission.objects.filter(is_active=True).values_list('codename', flat=True))

    cached = cache.get(_cache_key(user))
    if cached is not None:
        return cached

    employee = get_employee_profile(user)
    if employee is None:
        return set()

    perms = employee.permission_codenames()
    cache.set(_cache_key(user), perms, _CACHE_TTL)
    return perms


def has_enterprise_permission(user, codename):
    if not user or not user.is_authenticated:
        return False
    if not getattr(user, 'is_profile_approved', True):
        return False
    if user.is_superuser:
        return True
    if codename in SUPERUSER_ONLY_PERMISSIONS and not user.is_superuser:
        return False
    return codename in get_user_permission_codenames(user)


def legacy_module_grants_access(user, module_key):
    """Fallback when no employee profile — original role matrix."""
    from accounts.permissions import _ACCESS
    from accounts.rbac_service import permissions_for_role
    from accounts.roles import user_role

    role = user_role(user)
    if module_key in permissions_for_role(role):
        return True
    return module_key in _ACCESS.get(role, set())


def enterprise_module_grants_access(user, module_key):
    """Map legacy MODULE_* keys to enterprise permission codenames."""
    if module_key.startswith('dashboard_'):
        if has_enterprise_permission(user, 'dashboard'):
            return True
        # Field home is the landing page for technicians who already work Orders/WCR.
        if module_key == 'dashboard_engineer' and (
            has_enterprise_permission(user, 'orders')
            or has_enterprise_permission(user, 'wcr')
        ):
            return True
        return False

    codename = LEGACY_MODULE_TO_PERMISSION.get(module_key)
    if codename and has_enterprise_permission(user, codename):
        return True

    # Transition: profiles that only have Orders still reach Phase-1 ops modules
    # until dedicated fleet / special_projects / project_expenses grants are assigned.
    if module_key in ('special_projects', 'fleet', 'project_expenses',
                      'project_expenses_approve', 'project_expenses_manage'):
        if has_enterprise_permission(user, 'orders'):
            return True

    # PM is an observation layer on top of existing field operations.
    # Users who already work Orders / Scheduling / WCR should see it
    # even before a dedicated enterprise grant is assigned.
    if module_key in ('preventive_maintenance', 'preventive_maintenance_approve'):
        if has_enterprise_permission(user, 'preventive_maintenance'):
            return True
        if has_enterprise_permission(user, 'orders'):
            return True
        if has_enterprise_permission(user, 'scheduling'):
            return True
        if has_enterprise_permission(user, 'wcr'):
            return True
        if module_key == 'preventive_maintenance':
            from accounts.roles import is_field_staff
            if is_field_staff(getattr(user, 'role', None)):
                return True

    if codename:
        return False

    # Direct codename pass-through (future-proof)
    return has_enterprise_permission(user, module_key)


def can_access_via_enterprise(user, module_key):
    """Primary Phase 2 access check with legacy fallback."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_profile_approved', True):
        return False

    # Attendance self-service still driven by attendance_required flag
    if module_key == 'attendance_self':
        from attendance.permissions import user_requires_attendance
        if user_requires_attendance(user):
            return True

    if has_employee_profile(user):
        return enterprise_module_grants_access(user, module_key)

    return legacy_module_grants_access(user, module_key)


def _legacy_allowed_dashboard_url_name(user):
    """Role-based dashboard routing when no employee profile exists."""
    from accounts.permissions import has_full_access
    from accounts.roles import (
        ROLE_ACCOUNTS,
        ROLE_ACCOUNTS_EXECUTIVE,
        ROLE_BACK_OFFICE,
        ROLE_DIRECTOR,
        ROLE_ENGINEER,
        ROLE_OPERATIONS,
        ROLE_PROJECT_MANAGER,
        ROLE_SUPERVISOR,
        ROLE_TECHNICIAN,
        user_role,
    )

    if has_full_access(user) or user_role(user) == ROLE_DIRECTOR:
        return 'director_dashboard'
    role = user_role(user)
    if role == ROLE_OPERATIONS or role == ROLE_BACK_OFFICE:
        return 'operations_dashboard'
    if role in (ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE):
        return 'accounts_dashboard'
    if role == ROLE_PROJECT_MANAGER:
        return 'project_manager_dashboard'
    if role in (ROLE_ENGINEER, ROLE_TECHNICIAN):
        return 'field_team_dashboard'
    if role == ROLE_SUPERVISOR:
        return 'supervisor_dashboard'
    return 'login'


def allowed_dashboard_for_user(user):
    """Permission-based dashboard routing."""
    if not user or not user.is_authenticated:
        return 'login'
    if user.is_superuser:
        return 'director_dashboard'

    if has_employee_profile(user):
        perms = get_user_permission_codenames(user)
        if 'user_management' in perms or ('reports' in perms and 'billing' in perms):
            return 'director_dashboard'
        if perms & {'billing', 'payments', 'accounts'} and 'orders' not in perms:
            return 'accounts_dashboard'
        if 'orders' in perms and not (perms & {'billing', 'accounts'}):
            if perms & {'scheduling', 'wcr'} and 'quotation' not in perms:
                return 'field_team_dashboard'
            if 'approval' in perms and 'scheduling' in perms:
                return 'supervisor_dashboard'
            return 'operations_dashboard'
        if 'dashboard' in perms:
            return 'director_dashboard'
        # Incomplete enterprise grants — fall back to legacy role (never trap field staff on login)
        legacy = _legacy_allowed_dashboard_url_name(user)
        if legacy != 'login':
            return legacy
        if perms & {'orders', 'scheduling', 'wcr', 'gps_tracking'}:
            return 'field_team_dashboard'
        return 'login'

    return _legacy_allowed_dashboard_url_name(user)


def dashboard_widget_flags(user):
    """Permission-based dashboard section visibility."""
    if user.is_superuser:
        return {
            'show_operations': True,
            'show_financial': True,
            'show_quotations': True,
            'show_executive_kpis': True,
            'show_field_kpis': True,
            'show_attendance': True,
            'show_productivity': True,
            'show_reports': True,
        }

    perms = get_user_permission_codenames(user) if has_employee_profile(user) else set()
    if not perms:
        from accounts.permissions import can_manage_billing, can_view_quotations
        from accounts.roles import (
            ROLE_ACCOUNTS,
            ROLE_DIRECTOR,
            ROLE_ENGINEER,
            ROLE_SUPERVISOR,
            ROLE_TECHNICIAN,
            user_role,
        )
        role = user_role(user)
        return {
            'show_operations': role not in (ROLE_ACCOUNTS, 'ACCOUNTS_EXECUTIVE'),
            'show_financial': can_manage_billing(user),
            'show_quotations': can_view_quotations(user),
            'show_executive_kpis': role == ROLE_DIRECTOR,
            'show_field_kpis': role in (ROLE_ENGINEER, ROLE_TECHNICIAN, ROLE_SUPERVISOR),
            'show_attendance': True,
            'show_productivity': True,
            'show_reports': True,
        }

    return {
        'show_operations': bool(perms & {'orders', 'scheduling', 'wcr', 'boq'}),
        'show_financial': bool(perms & {'billing', 'payments', 'accounts'}),
        'show_quotations': 'quotation' in perms,
        'show_executive_kpis': bool(perms & {'reports', 'billing'}),
        'show_field_kpis': bool(perms & {'orders', 'scheduling', 'gps_tracking'}),
        'show_attendance': 'attendance' in perms,
        'show_productivity': 'reports' in perms,
        'show_reports': 'reports' in perms,
    }


# --- Permission-driven navigation ---

# Enterprise nav codename → legacy MODULE_* key (same path as page access / middleware)
ENTERPRISE_NAV_TO_MODULE = {
    'orders': 'orders',
    'scheduling': 'scheduling',
    'special_projects': 'special_projects',
    'fleet': 'fleet',
    'project_expenses': 'project_expenses',
    'preventive_maintenance': 'preventive_maintenance',
    'boq': 'boq',
    'wcr': 'wcr',
    'clients': 'clients',
    'quotation': 'quotations',
    'billing': 'manage_billing',
    'payments': 'manage_billing',
    'approval': 'user_approval',
    'masters': 'document_generator',
    'settings': 'company_settings',
    'reports': 'case_intelligence',
    'attendance': 'attendance_self',
    'gps_tracking': 'gps_tracking',
    'daily_meeting': 'daily_meetings',
    'hr': 'erms',
}

_DASHBOARD_MODULES = (
    'dashboard_director',
    'dashboard_operations',
    'dashboard_accounts',
    'dashboard_engineer',
    'dashboard_supervisor',
    'dashboard_project_manager',
)

NAV_MENU_CATALOG = [
    # section_label, permission, label, url_name, icon, nav_key, query_string
    ('', 'dashboard', 'Dashboard', '__dashboard__', 'bi-speedometer2', 'dashboard', ''),
    ('Operations', 'orders', 'Orders', 'order_list', 'bi-clipboard-check', 'orders', ''),
    ('Operations', 'preventive_maintenance', 'Preventive Maintenance', 'pm_dashboard', 'bi-tools', 'preventive_maintenance', ''),
    ('Operations', 'scheduling', 'Scheduling', 'schedule_list', 'bi-calendar-event', 'schedules', ''),
    ('Operations', 'special_projects', 'Special Projects', 'special_project_list', 'bi-kanban', 'special_projects', ''),
    ('Operations', 'fleet', 'Fleet & Fuel', 'fleet_dashboard', 'bi-fuel-pump', 'fleet', ''),
    ('Operations', 'project_expenses', 'Project Expenses', 'peams_dashboard', 'bi-cash-stack', 'project_expenses', ''),
    ('Operations', 'boq', 'BOQ', 'boq_list', 'bi-list-check', 'boq', ''),
    ('Operations', 'wcr', 'WCR', 'wcr_list', 'bi-file-earmark-text', 'wcr', ''),
    ('Customers', 'clients', 'Clients', 'client_list', 'bi-people', 'clients', ''),
    ('Finance', 'quotation', 'Quotations', 'quotation_list', 'bi-file-earmark-ruled', 'quotations', ''),
    ('Finance', 'billing', 'Billing', 'invoice_list', 'bi-receipt', 'billing', ''),
    ('Finance', 'billing', 'Manual Invoice Import', 'invoice_import_upload', 'bi-upload', 'invoice_import', ''),
    ('Finance', 'billing', 'Invoice Import History', 'invoice_import_history', 'bi-clock-history', 'invoice_import_history', ''),
    ('Finance', 'payments', 'Payments', 'invoice_list', 'bi-cash-coin', 'payments', 'status=PENDING'),
    ('Masters', 'approval', 'Employees', 'user_approval_list', 'bi-person-badge', 'user_approvals', ''),
    ('Masters', 'masters', 'Doc Numbers', 'document_control_panel', 'bi-hash', 'document_numbers', ''),
    ('Masters', 'settings', 'Company Settings', 'company_settings', 'bi-building-gear', 'company_settings', ''),
    ('Reports', 'reports', 'Reports', 'case_reports', 'bi-clipboard-data', 'reports', ''),
    ('Reports', 'reports', 'Case Intelligence', 'case_stuck_dashboard', 'bi-diagram-3', 'case_intelligence', ''),
    ('System', 'attendance', 'My Attendance', 'my_attendance', 'bi-person-check', 'attendance', ''),
    ('System', 'attendance', 'Attendance Management', 'attendance_dashboard', 'bi-calendar-check', 'attendance_mgmt', ''),
    ('System', 'attendance', 'Team Attendance', 'attendance_team', 'bi-people', 'attendance_team', ''),
    ('System', 'reports', 'Productivity', 'productivity_dashboard', 'bi-graph-up-arrow', 'productivity', ''),
    ('System', 'gps_tracking', 'GPS Tracking', 'gps_dashboard', 'bi-geo-alt', 'gps', ''),
    ('System', 'daily_meeting', 'Daily Meetings', 'dom_dashboard', 'bi-people-fill', 'daily_meetings', ''),
    ('System', 'hr', 'Requests', 'erms_dashboard', 'bi-inbox', 'employee_requests', ''),
]


def _can_access_nav_permission(user, permission):
    """Match sidebar visibility to page access (enterprise + legacy fallback)."""
    if permission == 'dashboard':
        dash = allowed_dashboard_for_user(user)
        if dash and dash != 'login':
            return True
        return any(can_access_via_enterprise(user, key) for key in _DASHBOARD_MODULES)

    module_key = ENTERPRISE_NAV_TO_MODULE.get(permission)
    if module_key:
        return can_access_via_enterprise(user, module_key)

    return has_enterprise_permission(user, permission)


def _nav_item_visible(user, permission, nav_key):
    """Visibility = module access (same as middleware) + item-specific rules."""
    if nav_key == 'attendance':
        from attendance.permissions import user_requires_attendance
        return (
            can_access_via_enterprise(user, 'attendance_self')
            and user_requires_attendance(user)
        )
    if nav_key == 'attendance_mgmt':
        from accounts.permissions import can_manage_attendance
        return can_manage_attendance(user)
    if nav_key == 'attendance_team':
        from accounts.permissions import can_view_team_attendance, can_manage_attendance
        return can_view_team_attendance(user) and not can_manage_attendance(user)
    if nav_key == 'document_numbers':
        return user.is_superuser or can_access_via_enterprise(user, 'user_management')
    if nav_key == 'user_approvals':
        return (
            can_access_via_enterprise(user, 'user_approval')
            or can_access_via_enterprise(user, 'user_management')
        )
    if nav_key == 'productivity':
        from productivity.permissions import can_view_management_productivity
        return can_view_management_productivity(user)
    if nav_key == 'employee_requests':
        from employee_requests.permissions import can_access_erms
        return can_access_erms(user)
    if nav_key == 'daily_meetings':
        from daily_meetings.permissions import can_access_daily_meetings
        return can_access_daily_meetings(user)
    if nav_key == 'preventive_maintenance':
        from preventive_maintenance.permissions import can_view_pm
        return can_view_pm(user) or _can_access_nav_permission(user, permission)

    return _can_access_nav_permission(user, permission)


def build_navigation_menu(user, dashboard_url_name='director_dashboard'):
    """Return permission-filtered nav sections for templates."""
    if not user or not user.is_authenticated:
        return []

    sections = []
    current_section = None
    section_items = []

    for section_label, permission, label, url_name, icon, nav_key, query in NAV_MENU_CATALOG:
        if not _nav_item_visible(user, permission, nav_key):
            continue

        if url_name == '__dashboard__':
            if not dashboard_url_name or dashboard_url_name == 'login':
                continue
            resolved_url = dashboard_url_name
            resolved_query = ''
        else:
            resolved_url = url_name
            resolved_query = query

        item = {
            'label': label,
            'url_name': resolved_url,
            'icon': icon,
            'nav_key': nav_key,
            'query': resolved_query,
            'badge': None,
        }

        if nav_key == 'user_approvals':
            from accounts.models import User
            from accounts.permissions import can_manage_user_approvals
            if can_manage_user_approvals(user):
                count = User.objects.filter(
                    approval_status=User.APPROVAL_PENDING,
                ).exclude(is_superuser=True).count()
                if count:
                    item['badge'] = count

        if nav_key == 'employee_requests':
            from employee_requests.permissions import can_access_erms
            if can_access_erms(user):
                from employee_requests.models import PortalNotification
                count = PortalNotification.objects.filter(user=user, is_read=False).count()
                if count:
                    item['badge'] = count

        if section_label != current_section:
            if section_items:
                sections.append({'label': current_section, 'items': section_items})
            current_section = section_label
            section_items = [item]
        else:
            section_items.append(item)

    if section_items:
        sections.append({'label': current_section, 'items': section_items})

    return _ensure_pm_nav_item(sections, user)


def _ensure_pm_nav_item(sections, user):
    """Always place Preventive Maintenance under Operations for eligible field/ops users."""
    from preventive_maintenance.permissions import can_view_pm

    if not can_view_pm(user):
        return sections
    for section in sections:
        if any(item.get('nav_key') == 'preventive_maintenance' for item in section.get('items', [])):
            return sections

    pm_item = {
        'label': 'Preventive Maintenance',
        'url_name': 'pm_dashboard',
        'icon': 'bi-tools',
        'nav_key': 'preventive_maintenance',
        'query': '',
        'badge': None,
    }
    for section in sections:
        if section.get('label') == 'Operations':
            items = section['items']
            insert_at = 0
            for index, item in enumerate(items):
                if item.get('nav_key') == 'orders':
                    insert_at = index + 1
                    break
            items.insert(insert_at, pm_item)
            return sections
    sections.append({'label': 'Operations', 'items': [pm_item]})
    return sections


def get_reporting_manager(user):
    """Approval hierarchy — reporting manager from employee profile."""
    employee = get_employee_profile(user)
    if employee and employee.reporting_manager_id:
        return employee.reporting_manager
    return getattr(user, 'reports_to', None)
