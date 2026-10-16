import traceback

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.management.base import BaseCommand
from django.db import connection
from django.test import RequestFactory

from accounts.enterprise_permissions import allowed_dashboard_for_user
from accounts.models import User
from dashboard import views as dashboard_views


_VIEWS = {
    'director_dashboard': dashboard_views.director_dashboard,
    'operations_dashboard': dashboard_views.operations_dashboard,
    'accounts_dashboard': dashboard_views.accounts_dashboard,
    'field_team_dashboard': dashboard_views.field_team_dashboard,
    'supervisor_dashboard': dashboard_views.supervisor_dashboard,
    'project_manager_dashboard': dashboard_views.project_manager_dashboard,
}


class Command(BaseCommand):
    help = 'Render each active user\'s home dashboard and print any traceback.'

    def handle(self, *args, **options):
        tables = set(connection.introspection.table_names())
        for name in ('task_manager_teamtask', 'task_manager_taskhistory'):
            self.stdout.write(f'TABLE {name} {"yes" if name in tables else "MISSING"}')

        users = list(User.objects.filter(is_active=True).order_by('id'))
        self.stdout.write(f'ACTIVE_USERS {len(users)}')
        if not users:
            self.stdout.write('NO_USERS')
            return

        factory = RequestFactory()
        failed = 0
        for user in users:
            url_name = allowed_dashboard_for_user(user)
            self.stdout.write(
                f'USER {user.username} role={user.role!r} '
                f'super={user.is_superuser} dash={url_name}'
            )
            view = _VIEWS.get(url_name)
            if view is None:
                self.stdout.write(f'SKIP {user.username} {url_name}')
                continue
            request = factory.get('/dashboard/')
            request.user = user
            SessionMiddleware(lambda r: None).process_request(request)
            request.session.save()
            MessageMiddleware(lambda r: None).process_request(request)
            try:
                response = view(request)
                if hasattr(response, 'render'):
                    response = response.render()
                self.stdout.write(f'STATUS {user.username} {response.status_code}')
                if response.status_code >= 500:
                    failed += 1
            except Exception:
                failed += 1
                self.stdout.write(f'FAIL {user.username}')
                self.stdout.write(traceback.format_exc())

        if failed:
            self.stdout.write(self.style.ERROR(f'DASHBOARD_FAILURES {failed}'))
        else:
            self.stdout.write(self.style.SUCCESS('DASHBOARD_OK'))
