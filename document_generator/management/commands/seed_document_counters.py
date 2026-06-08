from django.core.management.base import BaseCommand

from document_generator.services import seed_counters_from_existing


class Command(BaseCommand):
    help = 'Seed document counters from existing ITSPL-format numbers (does not modify records).'

    def handle(self, *args, **options):
        summary = seed_counters_from_existing()
        for doc_type, serial in summary.items():
            self.stdout.write(f'{doc_type}: current year series max serial = {serial}')
        self.stdout.write(self.style.SUCCESS('Document counters seeded.'))
