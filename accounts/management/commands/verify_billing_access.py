"""Verify finance-only billing access per role matrix."""

from django.core.management.base import BaseCommand

from accounts.permissions import can_manage_billing
from accounts.rbac_service import invalidate_rbac_cache
from billing.permissions import (
    can_approve_invoice,
    can_create_invoice,
    can_view_invoices,
)


class _User:
    is_authenticated = True
    is_superuser = False
    is_profile_approved = True

    def __init__(self, role, superuser=False):
        self.role = role
        self.is_superuser = superuser


# Only Admin/Superuser and Accounts Manager may access billing.
EXPECT_BILLING = {
    'SUPERUSER': True,
    'ACCOUNTS': True,
    'DIRECTOR': False,
    'OPERATIONS': False,
    'PROJECT_MANAGER': False,
    'SUPERVISOR': False,
    'ENGINEER': False,
    'Technician': False,
    'ACCOUNTS_EXECUTIVE': False,
    'BACK_OFFICE': False,
}


class Command(BaseCommand):
    help = 'Verify manage_billing access — finance-only billing module.'

    def handle(self, *args, **options):
        invalidate_rbac_cache()
        failures = []
        passes = 0

        checks = (
            ('menu', can_manage_billing),
            ('view', can_view_invoices),
            ('create', can_create_invoice),
            ('approve', can_approve_invoice),
            ('manage', can_manage_billing),
        )

        for role, expected in EXPECT_BILLING.items():
            if role == 'SUPERUSER':
                user = _User('ACCOUNTS', superuser=True)
            else:
                user = _User(role)

            for label, fn in checks:
                got = fn(user)
                if got == expected:
                    passes += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'PASS {role} {label}={expected}'
                    ))
                else:
                    failures.append(f'{role} {label}: expected {expected}, got {got}')

        self.stdout.write('')
        if failures:
            for f in failures:
                self.stdout.write(self.style.ERROR(f'  - {f}'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f'All {passes} billing access checks passed.'))
