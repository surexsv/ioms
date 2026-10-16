from django.db import migrations


def seed_task_permission(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    perm, _created = ModulePermission.objects.get_or_create(
        codename='task_manager',
        defaults={
            'name': 'Task Manager',
            'category': 'operations',
            'menu_url_name': 'task_dashboard',
            'menu_icon': 'bi-list-task',
            'sort_order': 46,
            'is_active': True,
            'is_system': True,
        },
    )
    Employee = apps.get_model('accounts', 'Employee')
    EmployeePermissionGrant = apps.get_model('accounts', 'EmployeePermissionGrant')
    for employee_id in Employee.objects.values_list('pk', flat=True):
        EmployeePermissionGrant.objects.get_or_create(
            employee_id=employee_id,
            permission=perm,
            defaults={
                'is_active': True,
                'notes': 'Seeded with Task Manager',
            },
        )


def unseed_task_permission(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    ModulePermission.objects.filter(codename='task_manager').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('task_manager', '0001_initial'),
        ('accounts', '0010_phase2_permission_menu_urls'),
    ]

    operations = [
        migrations.RunPython(seed_task_permission, unseed_task_permission),
    ]
