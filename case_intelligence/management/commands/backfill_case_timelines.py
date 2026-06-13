from django.core.management.base import BaseCommand

from case_intelligence.backfill import run_full_backfill


class Command(BaseCommand):
    help = 'Backfill Case Activity Timeline from existing database records (idempotent).'

    def handle(self, *args, **options):
        summary = run_full_backfill(stdout_write=self.stdout.write)
        self.stdout.write(self.style.SUCCESS(
            f'Done — {summary["total_created"]} new events, '
            f'{summary["total_skipped"]} duplicates skipped.',
        ))
