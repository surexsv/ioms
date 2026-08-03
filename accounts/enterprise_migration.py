"""Data migration helpers for enterprise user-management Phase 1."""

from django.utils import timezone

from accounts.enterprise_constants import (
    DEFAULT_DEPARTMENTS,
    DEFAULT_DESIGNATIONS,
    LEGACY_MODULE_TO_PERMISSION,
    LEGACY_ROLE_ORG_MAP,
    MODULE_PERMISSIONS,
    SUPERUSER_ONLY_PERMISSIONS,
)
from accounts.roles import normalize_role


def seed_masters(apps, schema_editor):
    Department = apps.get_model('accounts', 'Department')
    Designation = apps.get_model('accounts', 'Designation')
    Branch = apps.get_model('accounts', 'Branch')
    ModulePermission = apps.get_model('accounts', 'ModulePermission')

    for sort_order, (code, name) in enumerate(DEFAULT_DEPARTMENTS, start=1):
        Department.objects.get_or_create(
            code=code,
            defaults={'name': name, 'sort_order': sort_order, 'is_active': True},
        )

    for sort_order, (code, name) in enumerate(DEFAULT_DESIGNATIONS, start=1):
        Designation.objects.get_or_create(
            code=code,
            defaults={'name': name, 'sort_order': sort_order, 'is_active': True},
        )

    Branch.objects.get_or_create(
        code='HO',
        defaults={
            'name': 'Head Office',
            'city': '',
            'state': '',
            'is_head_office': True,
            'is_active': True,
        },
    )

    for sort_order, (codename, name, category) in enumerate(MODULE_PERMISSIONS, start=1):
        ModulePermission.objects.get_or_create(
            codename=codename,
            defaults={
                'name': name,
                'category': category,
                'sort_order': sort_order,
                'is_active': True,
                'is_system': True,
            },
        )


def _resolve_department_designation(apps, user):
    Department = apps.get_model('accounts', 'Department')
    Designation = apps.get_model('accounts', 'Designation')

    role = normalize_role(getattr(user, 'role', '') or '')
    if role in LEGACY_ROLE_ORG_MAP:
        dept_code, desig_code = LEGACY_ROLE_ORG_MAP[role]
        dept = Department.objects.filter(code=dept_code).first()
        desig = Designation.objects.filter(code=desig_code).first()
        if dept and desig:
            return dept, desig

    dept = None
    desig = None
    dept_text = (getattr(user, 'department', '') or '').strip().lower()
    desig_text = (getattr(user, 'designation', '') or '').strip().lower()
    if dept_text:
        dept = Department.objects.filter(name__iexact=dept_text).first()
        if not dept:
            dept = Department.objects.filter(code__iexact=dept_text.replace(' ', '_')).first()
    if desig_text:
        desig = Designation.objects.filter(name__iexact=desig_text).first()
        if not desig:
            desig = Designation.objects.filter(code__iexact=desig_text.replace(' ', '_').upper()).first()

    if not dept:
        dept = Department.objects.filter(code='OPERATIONS').first()
    if not desig:
        desig = Designation.objects.filter(code='ENGINEER').first()
    return dept, desig


def _legacy_permissions_for_role(role):
    from accounts.permissions import _ACCESS
    role = normalize_role(role or '')
    modules = _ACCESS.get(role, set())
    codenames = set()
    for module_key in modules:
        mapped = LEGACY_MODULE_TO_PERMISSION.get(module_key)
        if mapped:
            codenames.add(mapped)
    if role in ('ENGINEER', 'Technician', 'TECHNICIAN'):
        codenames.add('gps_tracking')
    if role in ('DIRECTOR', 'OPERATIONS', 'PROJECT_MANAGER', 'SUPERVISOR'):
        codenames.add('gps_tracking')
    return codenames


def migrate_users_to_employees(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Employee = apps.get_model('accounts', 'Employee')
    EmployeePermissionGrant = apps.get_model('accounts', 'EmployeePermissionGrant')
    Branch = apps.get_model('accounts', 'Branch')
    ModulePermission = apps.get_model('accounts', 'ModulePermission')

    head_office = Branch.objects.filter(is_head_office=True).first()
    if not head_office:
        head_office = Branch.objects.first()

    all_permissions = {p.codename: p for p in ModulePermission.objects.all()}

    for user in User.objects.all().iterator():
        if Employee.objects.filter(user_id=user.pk).exists():
            continue

        dept, desig = _resolve_department_designation(apps, user)
        if not dept or not desig or not head_office:
            continue

        code = (getattr(user, 'employee_id', '') or '').strip()
        if not code:
            code = f'EMP{user.pk:05d}'

        base_code = code
        suffix = 1
        while Employee.objects.filter(employee_code=code).exclude(user_id=user.pk).exists():
            code = f'{base_code}-{suffix}'
            suffix += 1

        if user.is_active and getattr(user, 'is_active_employee', True):
            status = 'ACTIVE'
        elif not user.is_active:
            status = 'TERMINATED'
        else:
            status = 'INACTIVE'

        joining_date = None
        if getattr(user, 'date_joined', None):
            joining_date = user.date_joined.date()

        employee = Employee.objects.create(
            user_id=user.pk,
            employee_code=code,
            department_id=dept.pk,
            designation_id=desig.pk,
            reporting_manager_id=getattr(user, 'reports_to_id', None),
            branch_id=head_office.pk,
            employment_type='FULL_TIME',
            mobile=getattr(user, 'phone', '') or '',
            joining_date=joining_date,
            status=status,
        )

        if user.is_superuser:
            grant_codenames = set(all_permissions.keys())
        else:
            grant_codenames = _legacy_permissions_for_role(getattr(user, 'role', ''))
            grant_codenames.discard(None)

        for codename in grant_codenames:
            perm = all_permissions.get(codename)
            if not perm:
                continue
            if codename in SUPERUSER_ONLY_PERMISSIONS and not user.is_superuser:
                continue
            EmployeePermissionGrant.objects.get_or_create(
                employee_id=employee.pk,
                permission_id=perm.pk,
                defaults={'is_active': True, 'granted_at': timezone.now()},
            )


def reverse_seed_masters(apps, schema_editor):
    pass


def reverse_migrate_users(apps, schema_editor):
    EmployeePermissionGrant = apps.get_model('accounts', 'EmployeePermissionGrant')
    Employee = apps.get_model('accounts', 'Employee')
    EmployeePermissionGrant.objects.all().delete()
    Employee.objects.all().delete()
