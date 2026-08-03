"""Enterprise user-management models — Phase 1.

Department, Designation, Branch, Employee profile, and individual permission grants.
Legacy User.role remains for backward compatibility until Phase 3.
"""

from django.conf import settings
from django.db import models


class Department(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Department'

    def __str__(self):
        return self.name


class Designation(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Designation'

    def __str__(self):
        return self.name


class Branch(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    is_head_office = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-is_head_office', 'name']
        verbose_name_plural = 'Branches'

    def __str__(self):
        return self.name


class ModulePermission(models.Model):
    """Permission master — assigned individually per employee (not via designation)."""

    codename = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    menu_url_name = models.CharField(
        max_length=80, blank=True,
        help_text='Django URL name for permission-driven menu (Phase 2).',
    )
    menu_icon = models.CharField(max_length=40, blank=True, default='bi-circle')
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(
        default=True,
        help_text='System permissions are seeded and should not be deleted.',
    )

    class Meta:
        ordering = ['sort_order', 'category', 'name']
        verbose_name = 'Module Permission'

    def __str__(self):
        return self.name


class Employee(models.Model):
    """Enterprise employee profile — one per login user."""

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_ON_LEAVE = 'ON_LEAVE'
    STATUS_TERMINATED = 'TERMINATED'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_ON_LEAVE, 'On Leave'),
        (STATUS_TERMINATED, 'Terminated'),
    )

    EMPLOYMENT_FULL_TIME = 'FULL_TIME'
    EMPLOYMENT_PART_TIME = 'PART_TIME'
    EMPLOYMENT_CONTRACT = 'CONTRACT'
    EMPLOYMENT_INTERN = 'INTERN'
    EMPLOYMENT_CONSULTANT = 'CONSULTANT'
    EMPLOYMENT_TYPE_CHOICES = (
        (EMPLOYMENT_FULL_TIME, 'Full Time'),
        (EMPLOYMENT_PART_TIME, 'Part Time'),
        (EMPLOYMENT_CONTRACT, 'Contract'),
        (EMPLOYMENT_INTERN, 'Intern'),
        (EMPLOYMENT_CONSULTANT, 'Consultant'),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile',
    )
    employee_code = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='employees',
    )
    designation = models.ForeignKey(
        Designation,
        on_delete=models.PROTECT,
        related_name='employees',
    )
    reporting_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enterprise_direct_reports',
        help_text='Approval hierarchy uses reporting manager, not designation.',
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name='employees',
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICES,
        default=EMPLOYMENT_FULL_TIME,
    )
    mobile = models.CharField(max_length=20, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    permissions = models.ManyToManyField(
        ModulePermission,
        through='EmployeePermissionGrant',
        related_name='employees',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_code']
        verbose_name = 'Employee'

    def __str__(self):
        return f'{self.employee_code} — {self.user.full_name_display}'

    @property
    def employee_name(self):
        return self.user.full_name_display

    @property
    def email(self):
        return self.user.email

    def permission_codenames(self):
        return set(
            self.permission_grants.filter(is_active=True)
            .values_list('permission__codename', flat=True)
        )

    def has_permission(self, codename):
        if self.user.is_superuser:
            return True
        return codename in self.permission_codenames()


class EmployeePermissionGrant(models.Model):
    """Individual permission assignment — not linked to designation."""

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='permission_grants',
    )
    permission = models.ForeignKey(
        ModulePermission,
        on_delete=models.CASCADE,
        related_name='grants',
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permission_grants_given',
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('employee', 'permission')
        ordering = ['permission__sort_order', 'permission__name']

    def __str__(self):
        return f'{self.employee.employee_code} → {self.permission.codename}'
