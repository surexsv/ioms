
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):

    ROLE_CHOICES = (
        ('DIRECTOR', 'Director'),
        ('OPERATIONS', 'Operations Manager'),
        ('PROJECT_MANAGER', 'Project Manager'),
        ('SUPERVISOR', 'Project Supervisor'),
        ('ACCOUNTS', 'Accounts Manager'),
        ('ACCOUNTS_EXECUTIVE', 'Accounts Executive'),
        ('BACK_OFFICE', 'Back Office Staff'),
        ('ENGINEER', 'Field Engineer'),
        ('Technician', 'Field Technician'),
        ('Supervisor', 'Field Supervisor (Legacy)'),
    )

    ROLE_REQUEST_CHOICES = (
        ('ENGINEER', 'Engineer'),
        ('OPERATIONS', 'Operations'),
        ('ACCOUNTS', 'Accounts'),
        ('MANAGER', 'Manager'),
    )

    APPROVAL_PENDING = 'PENDING'
    APPROVAL_APPROVED = 'APPROVED'
    APPROVAL_REJECTED = 'REJECTED'
    APPROVAL_STATUS_CHOICES = (
        (APPROVAL_PENDING, 'Pending'),
        (APPROVAL_APPROVED, 'Approved'),
        (APPROVAL_REJECTED, 'Rejected'),
    )

    ROLE_REQUEST_TO_SYSTEM = {
        'ENGINEER': 'ENGINEER',
        'OPERATIONS': 'OPERATIONS',
        'ACCOUNTS': 'ACCOUNTS',
        'MANAGER': 'PROJECT_MANAGER',
    }

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, default='')
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        help_text='Organizational reporting line (Director → Operations → PM → Supervisor).',
    )
    phone = models.CharField(max_length=15, blank=True)
    is_active_employee = models.BooleanField(default=True)
    attendance_required = models.BooleanField(
        default=True,
        help_text='When Yes, employee must mark daily attendance and sees the Attendance menu. '
                  'Directors and Admins should be set to No. Editable by Super User only.',
    )

    employee_id = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    role_requested = models.CharField(max_length=20, choices=ROLE_REQUEST_CHOICES, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_APPROVED,
    )
    approved_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users_approved',
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    resubmission_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.username

    @property
    def full_name_display(self):
        name = self.get_full_name().strip()
        return name or self.username

    @property
    def is_profile_approved(self):
        return self.is_superuser or self.approval_status == self.APPROVAL_APPROVED

    def map_requested_role(self):
        return self.ROLE_REQUEST_TO_SYSTEM.get(self.role_requested, 'ENGINEER')


class UserApprovalAuditLog(models.Model):
    ACTION_REGISTERED = 'REGISTERED'
    ACTION_RESUBMITTED = 'RESUBMITTED'
    ACTION_APPROVED = 'APPROVED'
    ACTION_REJECTED = 'REJECTED'

    ACTION_CHOICES = (
        (ACTION_REGISTERED, 'Registration Created'),
        (ACTION_RESUBMITTED, 'Profile Resubmitted'),
        (ACTION_APPROVED, 'Approved'),
        (ACTION_REJECTED, 'Rejected'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='approval_audit_logs',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_actions_performed',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} — {self.action}'


# RBAC models (imported for Django app registry)
from accounts.rbac_models import (  # noqa: E402, F401
    ActionPermission,
    MenuItem,
    RolePermission,
    SystemPermission,
    SystemRole,
)

# Enterprise user-management models (Phase 1)
from accounts.enterprise_models import (  # noqa: E402, F401
    Branch,
    Department,
    Designation,
    Employee,
    EmployeePermissionGrant,
    ModulePermission,
)
