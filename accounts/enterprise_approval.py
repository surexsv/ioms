"""Default permission grants when a registration is approved."""

from django.utils import timezone

from accounts.enterprise_constants import DESIGNATION_TO_LEGACY_ROLE, SUPERUSER_ONLY_PERMISSIONS
from accounts.enterprise_migration import _legacy_permissions_for_role
from accounts.enterprise_models import EmployeePermissionGrant, ModulePermission
from accounts.enterprise_permissions import invalidate_enterprise_permission_cache


def assign_default_permissions_on_approval(user):
    """Grant module permissions from designation/legacy role when none exist."""
    employee = getattr(user, 'employee_profile', None)
    if not employee:
        return

    if employee.permission_grants.filter(is_active=True).exists():
        return

    legacy_role = (getattr(user, 'role', '') or '').strip()
    if not legacy_role and employee.designation_id:
        legacy_role = DESIGNATION_TO_LEGACY_ROLE.get(employee.designation.code, '')

    grant_codenames = _legacy_permissions_for_role(legacy_role)
    if not grant_codenames:
        grant_codenames = {'dashboard', 'attendance'}

    permissions = {
        p.codename: p
        for p in ModulePermission.objects.filter(codename__in=grant_codenames, is_active=True)
    }

    for codename, perm in permissions.items():
        if codename in SUPERUSER_ONLY_PERMISSIONS:
            continue
        EmployeePermissionGrant.objects.get_or_create(
            employee=employee,
            permission=perm,
            defaults={'is_active': True, 'granted_at': timezone.now()},
        )

    invalidate_enterprise_permission_cache(user.pk)
