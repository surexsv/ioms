from django.core.management.base import BaseCommand

from task_manager.services import record_due_reminders


class Command(BaseCommand):
    help = 'Record reminders for team tasks that have reached their reminder date.'

    def handle(self, *args, **options):
        count = record_due_reminders()
        self.stdout.write(self.style.SUCCESS(f'Recorded {count} task reminder(s).'))
