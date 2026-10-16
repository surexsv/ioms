from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.enterprise_permissions import build_navigation_menu
from accounts.models import User

from .models import TaskHistory, TeamTask
from .services import create_task, record_due_reminders


class TaskManagerTests(TestCase):
    def setUp(self):
        self.tech = self.make_user('tech1', 'Technician')
        self.other = self.make_user('tech2', 'Technician')
        self.lead = self.make_user('lead1', 'SUPERVISOR')
        self.outsider = self.make_user('guest1', '')

    def make_user(self, username, role):
        return User.objects.create_user(
            username=username,
            password='test-pass',
            role=role,
            first_name=username,
            approval_status=User.APPROVAL_APPROVED,
            is_active_employee=True,
        )

    def test_create_schedule_remap_hold_remind_and_close(self):
        self.client.login(username='tech1', password='test-pass')
        tomorrow = timezone.localdate() + timedelta(days=1)
        due = tomorrow + timedelta(days=4)
        created = self.client.post(reverse('task_create'), {
            'title': 'Restore the site link',
            'description': 'Customer link is down at the hut.',
            'priority': TeamTask.PRIORITY_HIGH,
            'assignee': self.tech.pk,
            'scheduled_on': tomorrow.isoformat(),
            'due_on': due.isoformat(),
            'remind_after_days': 2,
            'remarks': 'Raised from the morning call.',
        })
        self.assertEqual(created.status_code, 302)
        task = TeamTask.objects.get()
        self.assertTrue(task.task_number.startswith('TM-'))
        self.assertEqual(task.status, TeamTask.STATUS_SCHEDULED)
        self.assertEqual(task.assignee, self.tech)
        self.assertEqual(task.next_reminder_on, tomorrow + timedelta(days=2))

        self.client.login(username='tech2', password='test-pass')
        hidden = self.client.get(reverse('task_detail', args=[task.pk]))
        self.assertEqual(hidden.status_code, 302)
        self.assertIn('/access-denied/', hidden.url)

        self.client.login(username='lead1', password='test-pass')
        visible = self.client.get(reverse('task_detail', args=[task.pk]))
        self.assertEqual(visible.status_code, 200)
        forwarded = self.client.post(reverse('task_detail', args=[task.pk]), {
            'action': 'remap',
            'remap-assignee': self.other.pk,
            'remap-remarks': 'Tech1 is stuck on another site.',
        })
        self.assertEqual(forwarded.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.assignee, self.other)
        remap = task.history.get(action=TaskHistory.ACTION_REMAPPED)
        self.assertEqual(remap.from_assignee, self.tech)
        self.assertEqual(remap.to_assignee, self.other)
        self.assertIn('stuck', remap.remarks)

        self.client.login(username='tech2', password='test-pass')
        missing_remarks = self.client.post(reverse('task_detail', args=[task.pk]), {
            'action': 'hold',
            'hold-remarks': '',
            'hold-remind_after_days': 3,
        })
        self.assertEqual(missing_remarks.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, TeamTask.STATUS_SCHEDULED)

        held = self.client.post(reverse('task_detail', args=[task.pk]), {
            'action': 'hold',
            'hold-remarks': 'Waiting for the spare fiber from stores.',
            'hold-remind_after_days': 1,
        })
        self.assertEqual(held.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, TeamTask.STATUS_ON_HOLD)
        self.assertIn('spare fiber', task.hold_remarks)

        task.next_reminder_on = timezone.localdate()
        task.save(update_fields=['next_reminder_on'])
        recorded = record_due_reminders()
        self.assertEqual(recorded, 1)
        self.assertTrue(task.history.filter(action=TaskHistory.ACTION_REMINDED).exists())
        task.refresh_from_db()
        self.assertEqual(task.next_reminder_on, timezone.localdate() + timedelta(days=1))
        self.assertEqual(record_due_reminders(), 0)

        resumed = self.client.post(reverse('task_detail', args=[task.pk]), {
            'action': 'resume',
            'resume-remarks': 'Spare fiber received.',
        })
        self.assertEqual(resumed.status_code, 302)
        closed = self.client.post(reverse('task_detail', args=[task.pk]), {
            'action': 'close',
            'close-remarks': 'Link restored and tested with the customer.',
        })
        self.assertEqual(closed.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, TeamTask.STATUS_CLOSED)
        self.assertIsNone(task.next_reminder_on)

        again = self.client.post(reverse('task_detail', args=[task.pk]), {
            'action': 'remap',
            'remap-assignee': self.tech.pk,
            'remap-remarks': 'Should not move a closed task.',
        })
        self.assertEqual(again.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.assignee, self.other)
        self.assertEqual(task.status, TeamTask.STATUS_CLOSED)

        history = self.client.get(reverse('task_history'), {'q': task.task_number})
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, 'Tech1 is stuck on another site.')
        self.assertContains(history, 'Link restored and tested with the customer.')
        self.assertContains(history, 'Reminder')

    def test_long_pending_is_flagged_for_hold(self):
        task = create_task(
            user=self.tech,
            title='Old pending job',
            description='Nobody has picked this up.',
            assignee=self.tech,
            remind_after_days=1,
        )
        task.created_at = timezone.now() - timedelta(days=3)
        task.save(update_fields=['created_at'])
        task.refresh_from_db()
        self.assertTrue(task.is_long_pending)
        self.client.login(username='tech1', password='test-pass')
        page = self.client.get(reverse('task_dashboard'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Pending Too Long')
        self.assertContains(page, task.task_number)

    def test_blank_role_cannot_open_task_manager(self):
        self.client.login(username='guest1', password='test-pass')
        response = self.client.get(reverse('task_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/access-denied/', response.url)

    def test_team_nav_includes_task_manager(self):
        from accounts.enterprise_models import ModulePermission
        self.assertTrue(ModulePermission.objects.filter(codename='task_manager', is_active=True).exists())
        nav_keys = {
            item['nav_key']
            for section in build_navigation_menu(self.tech, 'field_team_dashboard')
            for item in section.get('items', [])
        }
        self.assertIn('task_manager', nav_keys)
        self.client.login(username='tech1', password='test-pass')
        home = self.client.get(reverse('field_team_dashboard'))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, 'Task Manager')
        self.assertContains(home, reverse('task_dashboard'))

    def test_field_dashboard_survives_task_widget_failure(self):
        self.client.login(username='tech1', password='test-pass')
        with patch(
            'task_manager.services.dashboard_stats',
            side_effect=RuntimeError('task tables unavailable'),
        ):
            home = self.client.get(reverse('field_team_dashboard'))
        self.assertEqual(home.status_code, 200)
        self.assertNotContains(home, 'Reminded Today')
        self.assertContains(home, 'Task Manager')

    def test_reminder_command_skips_closed_tasks(self):
        task = create_task(
            user=self.lead,
            title='Already finished',
            description='Done before the reminder.',
            assignee=self.tech,
            remind_after_days=1,
        )
        task.status = TeamTask.STATUS_CLOSED
        task.next_reminder_on = timezone.localdate() - timedelta(days=1)
        task.save(update_fields=['status', 'next_reminder_on'])
        call_command('remind_team_tasks')
        self.assertFalse(task.history.filter(action=TaskHistory.ACTION_REMINDED).exists())
