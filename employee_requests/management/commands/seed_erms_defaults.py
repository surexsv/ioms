from django.core.management.base import BaseCommand

from employee_requests.constants import DEFAULT_REQUEST_TYPES
from employee_requests.models import RequestType


class Command(BaseCommand):
    help = 'Seed default ERMS request types.'

    def handle(self, *args, **options):
        for order, (code, name, requires_amount, hints) in enumerate(DEFAULT_REQUEST_TYPES):
            RequestType.objects.update_or_create(
                codename=code,
                defaults={
                    'name': name,
                    'requires_amount': requires_amount,
                    'approver_role_hints': hints,
                    'is_active': True,
                    'sort_order': order * 10,
                },
            )
        self.stdout.write(self.style.SUCCESS('ERMS request types seeded.'))
