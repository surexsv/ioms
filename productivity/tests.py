from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.enterprise_models import Branch, Department, Designation, Employee
from accounts.enterprise_permissions import build_navigation_menu
from accounts.models import User
from accounts.permissions import allowed_dashboard_url_name
from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
)
from attendance.models import Attendance
from productivity.calculator import compute_performance_score
from productivity.constants import ACT_ENQUIRY_PROCESSED, DEPT_OPERATIONS
from productivity.models import EmployeeActivityLog, EmployeeProductivitySnapshot, WCRTeamParticipant
from productivity.services import performance_scoreboard, save_director_marks
from wcr.models import WorkCompletionReport


class PerformanceScoreTests(TestCase):
    def test_full_field_month_with_director_mark_scores_100(self):
        score = compute_performance_score(
            jobs_attended=8,
            completed_jobs=8,
            activities_count=0,
            attendance_pct=100,
            attendance_required=True,
            wcr_submitted=4,
            man_days=20,
            director_mark=100,
        )
        self.assertEqual(score, Decimal('100.00'))

    def test_full_field_month_without_director_mark_scores_90(self):
        score = compute_performance_score(
            jobs_attended=8,
            completed_jobs=8,
            activities_count=0,
            attendance_pct=100,
            attendance_required=True,
            wcr_submitted=4,
            man_days=20,
        )
        self.assertEqual(score, Decimal('90.00'))

    def test_director_mark_is_ten_percent_of_the_score(self):
        score = compute_performance_score(director_mark=50)
        self.assertEqual(score, Decimal('5.00'))

    def test_partial_month_scores_below_a_full_month(self):
        full = compute_performance_score(
            jobs_attended=8,
            completed_jobs=8,
            attendance_pct=100,
            wcr_submitted=4,
            man_days=20,
        )
        partial = compute_performance_score(
            jobs_attended=8,
            completed_jobs=4,
            attendance_pct=50,
            wcr_submitted=2,
            man_days=10,
        )
        self.assertLess(partial, full)

    def test_office_work_scores_without_field_jobs(self):
        score = compute_performance_score(
            jobs_attended=0,
            completed_jobs=0,
            activities_count=12,
            attendance_pct=100,
            wcr_submitted=0,
            man_days=0,
        )
        self.assertEqual(score, Decimal('76.50'))

    def test_attendance_not_required_is_left_out_of_the_score(self):
        score = compute_performance_score(
            activities_count=12,
            attendance_pct=None,
            attendance_required=False,
        )
        self.assertEqual(score, Decimal('73.13'))


class ScoreboardTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.engineer = self._user('eng', ROLE_ENGINEER, 'Eng', 'One')
        self.manager = self._user('pm', ROLE_PROJECT_MANAGER, 'Pat', 'Manager')
        self.director = self._user('dir', ROLE_DIRECTOR, 'Dee', 'Director', attendance_required=False)
        self.tech = self._user('tech', ROLE_TECHNICIAN, 'Tech', 'One')
        self.accounts = self._user('acc', ROLE_ACCOUNTS, 'Ann', 'Accounts')
        self.inactive = self._user('old', ROLE_ENGINEER, 'Old', 'Hand', is_active_employee=False)

    def _user(self, username, role, first, last, **extra):
        return User.objects.create_user(
            username,
            password='secret',
            role=role,
            first_name=first,
            last_name=last,
            **extra,
        )

    def _log_activities(self, employee, count):
        for _ in range(count):
            EmployeeActivityLog.objects.create(
                activity_date=self.today,
                employee=employee,
                department=DEPT_OPERATIONS,
                activity_type=ACT_ENQUIRY_PROCESSED,
            )

    def test_board_includes_managers_and_saves_rank(self):
        wcr = WorkCompletionReport.objects.create(
            work_description='Install',
            submitted_by=self.engineer,
            completion_status='COMPLETED',
        )
        WorkCompletionReport.objects.filter(pk=wcr.pk).update(submitted_date=timezone.now())
        WCRTeamParticipant.objects.create(
            wcr=wcr,
            employee=self.engineer,
            participant_role='LEAD_ENGINEER',
            attended=True,
            hours_worked=Decimal('160'),
            man_days=Decimal('20'),
        )
        for day in range(1, 5):
            Attendance.objects.create(
                employee=self.engineer,
                attendance_date=date(self.today.year, self.today.month, day),
                status='PRESENT',
            )

        self._log_activities(self.manager, 12)
        Attendance.objects.create(
            employee=self.manager,
            attendance_date=self.today,
            status='PRESENT',
        )
        self._log_activities(self.director, 12)

        board = performance_scoreboard(self.today.year, self.today.month)
        ids = {row['employee_id'] for row in board}
        self.assertIn(self.manager.pk, ids)
        self.assertIn(self.director.pk, ids)
        self.assertIn(self.accounts.pk, ids)
        self.assertIn(self.tech.pk, ids)
        self.assertIn(self.engineer.pk, ids)
        self.assertNotIn(self.inactive.pk, ids)

        scores = [row['score'] for row in board]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(board[0]['rank'], 1)

        manager_row = next(row for row in board if row['employee_id'] == self.manager.pk)
        director_row = next(row for row in board if row['employee_id'] == self.director.pk)
        self.assertGreater(manager_row['score'], 0)
        self.assertGreater(director_row['score'], 0)
        self.assertEqual(manager_row['role_label'], 'Project Manager')
        self.assertEqual(director_row['role_label'], 'Director')

        zero_rows = [row for row in board if row['score'] == Decimal('0.00')]
        self.assertGreaterEqual(len(zero_rows), 2)
        self.assertEqual({row['rank'] for row in zero_rows}, {zero_rows[0]['rank']})

        snap = EmployeeProductivitySnapshot.objects.get(
            employee=self.manager,
            period_year=self.today.year,
            period_month=self.today.month,
        )
        self.assertEqual(snap.incentive_score, manager_row['score'])
        self.assertEqual(snap.ranking_position, manager_row['rank'])

    def test_dashboard_lists_manager_on_the_scoreboard(self):
        self._log_activities(self.manager, 4)
        self.client.force_login(self.director)
        response = self.client.get(reverse('productivity_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Performance Scoreboard')
        self.assertContains(response, 'Pat Manager')
        self.assertContains(response, 'Project Manager')
        self.assertContains(response, 'Ann Accounts')
        self.assertContains(response, 'Save director marks')
        self.assertContains(response, "Director's mark")

    def test_director_can_enter_a_mark_for_anyone(self):
        self._log_activities(self.manager, 12)
        Attendance.objects.create(
            employee=self.manager,
            attendance_date=self.today,
            status='PRESENT',
        )
        before = performance_scoreboard(self.today.year, self.today.month)
        before_score = next(row['score'] for row in before if row['employee_id'] == self.manager.pk)

        self.client.force_login(self.director)
        response = self.client.post(reverse('productivity_director_marks'), {
            'year': self.today.year,
            'month': self.today.month,
            f'mark-{self.manager.pk}': '80',
            f'note-{self.manager.pk}': 'Strong coordination',
            f'mark-{self.engineer.pk}': '100',
            f'note-{self.engineer.pk}': '',
        })
        self.assertEqual(response.status_code, 302)

        snap = EmployeeProductivitySnapshot.objects.get(
            employee=self.manager,
            period_year=self.today.year,
            period_month=self.today.month,
        )
        self.assertEqual(snap.director_mark, Decimal('80.00'))
        self.assertEqual(snap.director_mark_note, 'Strong coordination')
        self.assertEqual(snap.director_marked_by, self.director)
        self.assertEqual(snap.incentive_score, before_score + Decimal('8.00'))

        again = performance_scoreboard(self.today.year, self.today.month)
        kept = next(row for row in again if row['employee_id'] == self.manager.pk)
        self.assertEqual(kept['director_mark'], Decimal('80.00'))
        self.assertEqual(kept['score'], before_score + Decimal('8.00'))

        engineer_snap = EmployeeProductivitySnapshot.objects.get(
            employee=self.engineer,
            period_year=self.today.year,
            period_month=self.today.month,
        )
        self.assertEqual(engineer_snap.director_mark, Decimal('100.00'))

    def test_other_roles_cannot_enter_director_marks(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('productivity_director_marks'), {
            'year': self.today.year,
            'month': self.today.month,
            f'mark-{self.engineer.pk}': '90',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/access-denied', response.url)
        self.assertFalse(
            EmployeeProductivitySnapshot.objects.filter(director_mark__isnull=False).exists()
        )

    def test_mark_outside_range_is_rejected(self):
        self.client.force_login(self.director)
        response = self.client.post(reverse('productivity_director_marks'), {
            'year': self.today.year,
            'month': self.today.month,
            f'mark-{self.manager.pk}': '150',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'must be from 0 to 100')
        self.assertFalse(
            EmployeeProductivitySnapshot.objects.filter(director_mark__isnull=False).exists()
        )

    def test_manager_sees_the_mark_but_not_the_editor(self):
        save_director_marks(
            self.director,
            self.today.year,
            self.today.month,
            {self.manager.pk: Decimal('80')},
            {self.manager.pk: 'Steady month'},
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('productivity_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '80.00')
        self.assertContains(response, 'Steady month')
        self.assertNotContains(response, 'Save director marks')

    def test_technician_sees_scoreboard_in_the_menu_and_can_open_it(self):
        department = Department.objects.create(code='FIELD-SB', name='Field')
        designation = Designation.objects.create(code='TECH-SB', name='Technician')
        branch = Branch.objects.create(code='SB-HO', name='Scoreboard Office')
        Employee.objects.create(
            user=self.tech,
            employee_code='TECH-1',
            department=department,
            designation=designation,
            branch=branch,
        )
        menu = build_navigation_menu(self.tech, allowed_dashboard_url_name(self.tech))
        labels = {item['label'] for section in menu for item in section['items']}
        self.assertIn('Scoreboard', labels)

        self.client.force_login(self.tech)
        response = self.client.get(reverse('productivity_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Performance Scoreboard')
        self.assertContains(response, 'Pat Manager')
        self.assertNotContains(response, 'Save director marks')

    def test_director_dashboard_shows_the_scoreboard(self):
        self._log_activities(self.manager, 4)
        self.client.force_login(self.director)
        response = self.client.get(reverse('director_dashboard'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Performance Scoreboard', html)
        self.assertIn('Open Scoreboard', html)
        self.assertIn('>Scoreboard<', html)
        self.assertIn('Pat Manager', html)
        self.assertLess(html.index('id="performance-scoreboard"'), html.index('Case Monitoring'))
        menu = build_navigation_menu(self.director, allowed_dashboard_url_name(self.director))
        operations = next(section for section in menu if section['label'] == 'Operations')
        self.assertEqual(operations['items'][0]['label'], 'Scoreboard')

    def test_every_role_dashboard_opens_with_the_scoreboard(self):
        supervisor = self._user('sup', ROLE_SUPERVISOR, 'Sam', 'Supervisor')
        operations = self._user('ops', ROLE_OPERATIONS, 'Olive', 'Ops')
        pages = (
            (self.director, 'director_dashboard'),
            (operations, 'operations_dashboard'),
            (self.accounts, 'accounts_dashboard'),
            (self.manager, 'project_manager_dashboard'),
            (supervisor, 'supervisor_dashboard'),
            (self.engineer, 'field_team_dashboard'),
            (self.tech, 'field_team_dashboard'),
        )
        for user, url_name in pages:
            self.client.force_login(user)
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)
            html = response.content.decode()
            self.assertIn('id="performance-scoreboard"', html, url_name)
            self.assertIn('Performance Scoreboard', html, url_name)
            self.assertLess(
                html.index('id="performance-scoreboard"'),
                html.index('ioms-kpi-grid'),
                url_name,
            )
