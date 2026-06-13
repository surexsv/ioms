"""Verify separated attendance menu visibility per role matrix."""

from django.core.management.base import BaseCommand

from accounts.permissions import (
    show_nav_my_attendance,
    show_nav_attendance_management,
    show_nav_team_attendance,
)
from accounts.rbac_service import invalidate_rbac_cache
from attendance.permissions import user_requires_attendance


class _User:
    is_authenticated = True
    is_superuser = False
    is_profile_approved = True
    attendance_required = True

    def __init__(self, role, superuser=False, attendance_required=True):
        self.role = role
        self.is_superuser = superuser
        self.attendance_required = attendance_required


EXPECT = {
    'SUPERUSER': dict(my=False, mgmt=True, team=False),
    'DIRECTOR': dict(my=False, mgmt=True, team=False, attendance_required=False),
    'OPERATIONS': dict(my=True, mgmt=False, team=True),
    'PROJECT_MANAGER': dict(my=True, mgmt=False, team=True),
    'SUPERVISOR': dict(my=True, mgmt=False, team=True),
    'ACCOUNTS': dict(my=True, mgmt=True, team=False),
    'ACCOUNTS_EXECUTIVE': dict(my=True, mgmt=False, team=False),
    'ENGINEER': dict(my=True, mgmt=False, team=False),
    'Technician': dict(my=True, mgmt=False, team=False),
    'BACK_OFFICE': dict(my=True, mgmt=False, team=False),
}


class Command(BaseCommand):
    help = 'Verify My Attendance vs Attendance Management menu separation.'

    def handle(self, *args, **options):
        invalidate_rbac_cache()
        failures = []
        passes = 0

        for role, exp in EXPECT.items():
            if role == 'SUPERUSER':
                user = _User('OPERATIONS', superuser=True)
            elif role == 'DIRECTOR':
                user = _User(role, attendance_required=exp.get('attendance_required', True))
            else:
                user = _User(role)

            got = {
                'my': show_nav_my_attendance(user),
                'mgmt': show_nav_attendance_management(user),
                'team': show_nav_team_attendance(user),
            }
            for key in ('my', 'mgmt', 'team'):
                if got[key] == exp[key]:
                    passes += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'PASS {role} {key}={exp[key]}'
                    ))
                else:
                    failures.append(f'{role} {key}: expected {exp[key]}, got {got[key]}')

        self.stdout.write('')
        if failures:
            for f in failures:
                self.stdout.write(self.style.ERROR(f'  - {f}'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f'All {passes} menu checks passed.'))
