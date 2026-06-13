"""Set attendance_required defaults for existing users (idempotent)."""
from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = 'Set attendance_required: False for Admin/Superuser/Director; True for all other active employees.'

    def handle(self, *args, **options):
        updated = 0
        for user in User.objects.all():
            if user.is_superuser:
                required = False
            elif user.role == 'DIRECTOR':
                required = False
            elif user.is_active and user.is_active_employee:
                required = True
            else:
                required = False
            if user.attendance_required != required:
                user.attendance_required = required
                user.save(update_fields=['attendance_required'])
                updated += 1
                self.stdout.write(f'  {user.username}: attendance_required={required}')
        self.stdout.write(self.style.SUCCESS(
            f'Attendance eligibility update complete. Updated {updated} user(s).',
        ))
