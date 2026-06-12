from django.core.management.base import BaseCommand

from billing.gst import resolve_client_gst_type, sync_client_gst_fields
from clients.models import Client


class Command(BaseCommand):
    help = (
        'Sync client state, state code, and GST type from GSTIN / state. '
        'Safe to run on existing records — does not delete clients.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show changes without saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        updated = 0
        for client in Client.objects.all().order_by('name'):
            before = (
                client.state, client.state_code,
                client.gst_type or resolve_client_gst_type(client),
                client.pan_number,
            )
            sync_client_gst_fields(client, save=False)
            after = (
                client.state, client.state_code,
                client.gst_type or resolve_client_gst_type(client),
                client.pan_number,
            )
            if before != after:
                updated += 1
                self.stdout.write(
                    f'{client.name}: state={after[0]!r} code={after[1]!r} '
                    f'gst_type={after[2]} pan={after[3]!r}'
                )
                if not dry_run:
                    client.save(update_fields=['state', 'state_code', 'gst_type', 'pan_number'])

        self.stdout.write(self.style.SUCCESS(
            f'{"Would update" if dry_run else "Updated"} {updated} client(s).'
        ))
