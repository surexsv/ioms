"""Re-seed enterprise masters and optionally re-sync employee permissions from legacy roles."""

from django.core.management.base import BaseCommand

from accounts.enterprise_migration import migrate_users_to_employees, seed_masters


class Command(BaseCommand):
    help = 'Seed Department, Designation, Branch, ModulePermission masters and sync Employee profiles.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sync-employees',
            action='store_true',
            help='Create missing Employee profiles and permission grants from legacy User.role.',
        )

    def handle(self, *args, **options):
        from django.apps import apps
        seed_masters(apps, None)
        self.stdout.write(self.style.SUCCESS('Enterprise masters seeded.'))

        if options['sync_employees']:
            migrate_users_to_employees(apps, None)
            self.stdout.write(self.style.SUCCESS('Employee profiles synced from users.'))
