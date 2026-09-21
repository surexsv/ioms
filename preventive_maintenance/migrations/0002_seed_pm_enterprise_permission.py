from django.db import migrations


def seed_pm_permission(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    perm, _ = ModulePermission.objects.get_or_create(
        codename='preventive_maintenance',
        defaults={
            'name': 'Preventive Maintenance',
            'category': 'operations',
            'menu_url_name': 'pm_dashboard',
            'menu_icon': 'bi-tools',
            'sort_order': 45,
            'is_active': True,
            'is_system': True,
        },
    )
    if not perm.menu_url_name:
        perm.menu_url_name = 'pm_dashboard'
        perm.menu_icon = perm.menu_icon or 'bi-tools'
        perm.save(update_fields=['menu_url_name', 'menu_icon'])

    EmployeePermissionGrant = apps.get_model('accounts', 'EmployeePermissionGrant')
    Employee = apps.get_model('accounts', 'Employee')
    related_codenames = ('orders', 'scheduling', 'wcr')
    employee_ids = Employee.objects.filter(
        permission_grants__is_active=True,
        permission_grants__permission__codename__in=related_codenames,
    ).distinct().values_list('pk', flat=True)
    for employee_id in employee_ids:
        EmployeePermissionGrant.objects.get_or_create(
            employee_id=employee_id,
            permission=perm,
            defaults={'is_active': True, 'notes': 'Seeded with Preventive Maintenance module'},
        )


def unseed_pm_permission(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('preventive_maintenance', '0001_preventive_maintenance_phase1'),
        ('accounts', '0010_phase2_permission_menu_urls'),
    ]

    operations = [
        migrations.RunPython(seed_pm_permission, unseed_pm_permission),
    ]
