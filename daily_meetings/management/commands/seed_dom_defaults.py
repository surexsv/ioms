from django.core.management.base import BaseCommand

from daily_meetings.services import seed_agenda_template, seed_open_items


class Command(BaseCommand):
    help = 'Seed default agenda template and recurring open items for Daily Meetings.'

    def handle(self, *args, **options):
        agenda = seed_agenda_template()
        items = seed_open_items()
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {agenda} agenda item(s) and {items} open item(s).',
        ))
