"""Verify attendance audit data visibility per role matrix."""

from django.core.management.base import BaseCommand

from accounts.permissions import can_view_attendance_audit_data
from accounts.rbac_service import invalidate_rbac_cache


class _User:
    is_authenticated = True
    is_superuser = False
    is_profile_approved = True

    def __init__(self, role, superuser=False):
        self.role = role
        self.is_superuser = superuser


EXPECT_AUDIT_ACCESS = {
    'SUPERUSER': True,
    'DIRECTOR': True,
    'OPERATIONS': False,
    'PROJECT_MANAGER': False,
    'SUPERVISOR': False,
    'ACCOUNTS': False,
    'ACCOUNTS_EXECUTIVE': False,
    'ENGINEER': False,
    'Technician': False,
    'BACK_OFFICE': False,
}


class Command(BaseCommand):
    help = 'Verify view_attendance_audit_data — Director and Admin/Superuser only.'

    def handle(self, *args, **options):
        invalidate_rbac_cache()
        failures = []
        passes = 0

        for role, expected in EXPECT_AUDIT_ACCESS.items():
            if role == 'SUPERUSER':
                user = _User('DIRECTOR', superuser=True)
            else:
                user = _User(role)

            got = can_view_attendance_audit_data(user)
            if got == expected:
                passes += 1
                self.stdout.write(self.style.SUCCESS(
                    f'PASS {role} audit_access={expected}'
                ))
            else:
                failures.append(f'{role}: expected {expected}, got {got}')

        self.stdout.write('')
        if failures:
            for f in failures:
                self.stdout.write(self.style.ERROR(f'  - {f}'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(
            f'All {passes} attendance audit access checks passed.'
        ))
