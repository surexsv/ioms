from django.core.management.base import BaseCommand
from accounts.models import User
from clients.models import Client
from orders.models import Order
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Create demo admin user and sample data for testing the OMS portal'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@infomates.com',
                'role': 'DIRECTOR',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS('Created user admin / admin123'))
        else:
            self.stdout.write('User admin already exists')

        client, _ = Client.objects.get_or_create(
            name='Demo Telecom Pvt Ltd',
            defaults={
                'company_type': 'TELECOM',
                'address': '123 MG Road, Bangalore',
                'contact_person': 'Raj Kumar',
                'phone': '9876543210',
            },
        )

        if not Order.objects.filter(client=client).exists():
            engineer, _ = User.objects.get_or_create(
                username='engineer1',
                defaults={
                    'email': 'eng@infomates.com',
                    'role': 'ENGINEER',
                },
            )
            if _:
                engineer.set_password('engineer123')
                engineer.save()

            from scheduling.models import WorkSchedule
            order = Order.objects.create(
                client=client,
                project_site_name='Whitefield Fiber Site',
                site_address='Site A, Whitefield',
                order_type='INSTALLATION',
                description='Fiber installation at client premises',
                priority='High',
                expected_completion_date=date.today() + timedelta(days=7),
                status='NEW',
            )
            schedule = WorkSchedule.objects.create(
                order=order,
                scheduled_start_date=date.today(),
                scheduled_end_date=date.today() + timedelta(days=7),
                status=WorkSchedule.STATUS_ASSIGNED,
            )
            schedule.assigned_engineers.add(engineer)
            self.stdout.write(self.style.SUCCESS('Sample client and order created'))

        supervisor, created = User.objects.get_or_create(
            username='supervisor1',
            defaults={
                'email': 'supervisor@infomates.com',
                'role': 'Supervisor',
            },
        )
        if created:
            supervisor.set_password('supervisor123')
            supervisor.save()
            self.stdout.write(self.style.SUCCESS('Created supervisor1 / supervisor123'))
