from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_PROJECT_MANAGER,
    ROLE_TECHNICIAN,
)
from attendance.models import Attendance
from productivity.calculator import compute_performance_score
from productivity.constants import ACT_ENQUIRY_PROCESSED, DEPT_OPERATIONS
from productivity.models import EmployeeActivityLog, EmployeeProductivitySnapshot, WCRTeamParticipant
from productivity.services import performance_scoreboard
from wcr.models import WorkCompletionReport


class PerformanceScoreTests(TestCase):
    def test_full_field_month_scores_100(self):
        score = compute_performance_score(
            jobs_attended=8,
            completed_jobs=8,
            activities_count=0,
            attendance_pct=100,
            attendance_required=True,
            wcr_submitted=4,
            man_days=20,
        )
        self.assertEqual(score, Decimal('100.00'))

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
        self.assertEqual(score, Decimal('85.00'))

    def test_attendance_not_required_is_left_out_of_the_score(self):
        score = compute_performance_score(
            activities_count=12,
            attendance_pct=None,
            attendance_required=False,
        )
        self.assertEqual(score, Decimal('81.25'))


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
