"""Technician / engineer participation in Daily Meetings."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.roles import ROLE_OPERATIONS, ROLE_SUPERVISOR, ROLE_TECHNICIAN
from attendance.permissions import default_attendance_required_for_role

from accounts.enterprise_permissions import build_navigation_menu
from accounts.permissions import (
    MODULE_DAILY_MEETINGS,
    MODULE_DAILY_MEETINGS_MANAGE,
    allowed_dashboard_url_name,
    resolve_path_module,
)

from .models import MeetingActionItem, MeetingAttendance, MeetingDiscussion
from .services import create_daily_meeting

PASSWORD = 'testpass123'


class DailyMeetingParticipantTests(TestCase):
    def setUp(self):
        self.ops = User.objects.create_user(
            username='ops1',
            password=PASSWORD,
            role=ROLE_OPERATIONS,
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
            attendance_required=default_attendance_required_for_role(ROLE_OPERATIONS),
        )
        self.tech = User.objects.create_user(
            username='tech1',
            password=PASSWORD,
            role=ROLE_TECHNICIAN,
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
            attendance_required=default_attendance_required_for_role(ROLE_TECHNICIAN),
        )
        self.supervisor = User.objects.create_user(
            username='sup1',
            password=PASSWORD,
            role=ROLE_SUPERVISOR,
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
            attendance_required=default_attendance_required_for_role(ROLE_SUPERVISOR),
        )
        self.meeting, _ = create_daily_meeting(self.ops, topic_of_day='Safety briefing')
        self.action = MeetingActionItem.objects.create(
            meeting=self.meeting,
            description='Check site toolbox',
            assigned_to=self.tech,
            created_by=self.ops,
            target_date=timezone.localdate(),
        )

    def test_technician_opens_dashboard_and_meeting_not_action_tracker(self):
        self.client.force_login(self.tech)
        dashboard = self.client.get(reverse('dom_dashboard'))
        self.assertEqual(dashboard.status_code, 302)
        self.assertEqual(dashboard.url, reverse('dom_meeting_today'))
        today = self.client.get(dashboard.url)
        self.assertEqual(today.status_code, 302)
        self.assertIn(f'/daily-meetings/meetings/{self.meeting.pk}/', today.url)

        listing = self.client.get(reverse('dom_meeting_list'))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, self.meeting.meeting_number)

        detail = self.client.get(reverse('dom_meeting_detail', args=[self.meeting.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Enter meeting details')
        self.assertContains(detail, 'Save meeting details')
        self.assertContains(detail, 'Check site toolbox')
        menu = build_navigation_menu(self.tech, allowed_dashboard_url_name(self.tech))
        urls = {item['url_name'] for section in menu for item in section['items']}
        self.assertIn('dom_meeting_today', urls)
        self.assertNotIn('dom_dashboard', urls)

    def test_technician_cannot_create_or_manage_meeting(self):
        self.client.force_login(self.tech)
        create = self.client.get(reverse('dom_meeting_create'))
        self.assertIn(create.status_code, {302, 403})
        if create.status_code in {301, 302, 303}:
            self.assertIn('access-denied', create.url)
        edit = self.client.get(reverse('dom_meeting_edit', args=[self.meeting.pk]))
        self.assertIn(edit.status_code, {302, 403})

    def test_technician_can_open_todays_meeting_from_action_tracker(self):
        self.client.force_login(self.tech)
        tracker = self.client.get(reverse('dom_action_tracker'))
        self.assertEqual(tracker.status_code, 200)
        self.assertContains(tracker, 'Enter meeting details')
        today = self.client.get(reverse('dom_meeting_today'))
        self.assertEqual(today.status_code, 302)
        self.assertIn(f'/daily-meetings/meetings/{self.meeting.pk}/', today.url)
        detail = self.client.get(today.url)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Enter meeting details')
        self.assertContains(detail, 'Save meeting details')

    def test_technician_saves_meeting_details_on_the_meeting_page(self):
        self.client.force_login(self.tech)
        url = reverse('dom_meeting_detail', args=[self.meeting.pk])
        response = self.client.post(url, {
            'participant_action': 'save_details',
            'topic_of_day': 'Site safety',
            'remarks': 'Checked toolbox and PPE',
        })
        self.assertEqual(response.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.topic_of_day, 'Site safety')
        self.assertEqual(self.meeting.remarks, 'Checked toolbox and PPE')

        att = MeetingAttendance.objects.get(meeting=self.meeting, employee=self.tech)
        response = self.client.post(url, {
            'participant_action': 'save_attendance',
            'status': MeetingAttendance.STATUS_PRESENT,
            'join_time': '09:05',
            'remarks': 'Joined from site',
        })
        self.assertEqual(response.status_code, 302)
        att.refresh_from_db()
        self.assertEqual(att.status, MeetingAttendance.STATUS_PRESENT)

        response = self.client.post(url, {
            'participant_action': 'add_update',
            'discussion_notes': 'Fiber splicing completed on span 12',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            MeetingDiscussion.objects.filter(
                meeting=self.meeting,
                discussion_notes='Fiber splicing completed on span 12',
            ).exists()
        )

    def test_technician_enters_own_attendance(self):
        self.client.force_login(self.tech)
        self.client.get(reverse('dom_meeting_detail', args=[self.meeting.pk]))
        att = MeetingAttendance.objects.get(meeting=self.meeting, employee=self.tech)
        url = reverse('dom_meeting_attendance_edit', args=[self.meeting.pk, att.pk])
        response = self.client.post(url, {
            'status': MeetingAttendance.STATUS_PRESENT,
            'join_time': '09:05',
            'remarks': 'Joined from site',
        })
        self.assertEqual(response.status_code, 302)
        att.refresh_from_db()
        self.assertEqual(att.status, MeetingAttendance.STATUS_PRESENT)
        self.assertEqual(att.remarks, 'Joined from site')
        self.assertTrue(att.is_manual_override)

    def test_technician_cannot_edit_someone_elses_attendance(self):
        other, _ = MeetingAttendance.objects.get_or_create(
            meeting=self.meeting,
            employee=self.ops,
            defaults={'status': MeetingAttendance.STATUS_ABSENT},
        )
        self.client.force_login(self.tech)
        response = self.client.get(
            reverse('dom_meeting_attendance_edit', args=[self.meeting.pk, other.pk])
        )
        self.assertIn(response.status_code, {302, 403})

    def test_technician_updates_own_action_progress_only(self):
        self.client.force_login(self.tech)
        url = reverse('dom_action_edit', args=[self.action.pk])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'name="assigned_to"')
        response = self.client.post(url, {
            'status': MeetingActionItem.STATUS_COMPLETED,
            'remarks': 'Toolbox checked',
            'completion_date': timezone.localdate().isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, MeetingActionItem.STATUS_COMPLETED)
        self.assertEqual(self.action.assigned_to, self.tech)
        self.assertEqual(self.action.description, 'Check site toolbox')

    def test_participant_edit_urls_are_not_mapped_to_manage_module(self):
        self.assertEqual(
            resolve_path_module('/daily-meetings/actions/1/edit/'),
            MODULE_DAILY_MEETINGS,
        )
        self.assertEqual(
            resolve_path_module('/daily-meetings/meetings/1/attendance/3/edit/'),
            MODULE_DAILY_MEETINGS,
        )
        self.assertEqual(
            resolve_path_module('/daily-meetings/meetings/1/edit/'),
            MODULE_DAILY_MEETINGS_MANAGE,
        )
        self.assertEqual(
            resolve_path_module('/daily-meetings/meetings/create/'),
            MODULE_DAILY_MEETINGS_MANAGE,
        )
        self.assertEqual(
            resolve_path_module('/daily-meetings/meetings/today/'),
            MODULE_DAILY_MEETINGS,
        )

    def test_supervisor_without_module_cannot_open_daily_meetings(self):
        self.client.force_login(self.supervisor)
        response = self.client.get(reverse('dom_dashboard'))
        self.assertIn(response.status_code, {302, 403})
        if response.status_code in {301, 302, 303}:
            self.assertIn('access-denied', response.url)
