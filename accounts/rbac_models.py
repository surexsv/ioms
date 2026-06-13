"""Database-backed RBAC — Role → Permissions → Menus → Actions."""

from django.db import models


class SystemRole(models.Model):
    """Organizational role (maps to User.role codename)."""

    codename = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=80)
    hierarchy_level = models.PositiveSmallIntegerField(
        default=100,
        help_text='Lower number = higher authority (Admin=0, Director=10, …)',
    )
    is_system = models.BooleanField(
        default=True,
        help_text='System roles are seeded and should not be deleted.',
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['hierarchy_level', 'name']

    def __str__(self):
        return self.name


class SystemPermission(models.Model):
    """Granular permission (maps to MODULE_* keys and action codenames)."""

    codename = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'codename']

    def __str__(self):
        return f'{self.name} ({self.codename})'


class RolePermission(models.Model):
    role = models.ForeignKey(SystemRole, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(
        SystemPermission, on_delete=models.CASCADE, related_name='role_permissions',
    )

    class Meta:
        unique_together = ('role', 'permission')

    def __str__(self):
        return f'{self.role.codename} → {self.permission.codename}'


class MenuItem(models.Model):
    """Sidebar / navigation entry gated by permission."""

    label = models.CharField(max_length=60)
    url_name = models.CharField(max_length=80, blank=True)
    icon = models.CharField(max_length=40, blank=True, default='bi-circle')
    permission = models.ForeignKey(
        SystemPermission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='menu_items',
        help_text='User must have this permission to see the menu item.',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    nav_key = models.CharField(
        max_length=40, blank=True,
        help_text='Matches nav_active key in context processor (e.g. enquiries).',
    )

    class Meta:
        ordering = ['sort_order', 'label']

    def __str__(self):
        return self.label


class ActionPermission(models.Model):
    """URL/view action mapped to a required permission."""

    label = models.CharField(max_length=80, blank=True)
    url_pattern = models.CharField(
        max_length=200, blank=True,
        help_text='Path prefix, e.g. /enquiries/create/',
    )
    view_name = models.CharField(max_length=80, blank=True)
    http_method = models.CharField(max_length=10, default='GET')
    permission = models.ForeignKey(
        SystemPermission, on_delete=models.CASCADE, related_name='actions',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['url_pattern']

    def __str__(self):
        return self.label or self.url_pattern or self.view_name
