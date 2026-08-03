# Generated manually for Phase 2 — populate menu_url_name on ModulePermission

from django.db import migrations

PERMISSION_MENU_MAP = {
    'dashboard': ('__dashboard__', 'bi-speedometer2'),
    'clients': ('client_list', 'bi-people'),
    'orders': ('order_list', 'bi-clipboard-check'),
    'scheduling': ('schedule_list', 'bi-calendar-event'),
    'boq': ('boq_list', 'bi-list-check'),
    'wcr': ('wcr_list', 'bi-file-earmark-text'),
    'quotation': ('quotation_list', 'bi-file-earmark-ruled'),
    'billing': ('invoice_list', 'bi-receipt'),
    'payments': ('invoice_list', 'bi-cash-coin'),
    'approval': ('user_approval_list', 'bi-person-badge'),
    'masters': ('document_control_panel', 'bi-hash'),
    'settings': ('company_settings', 'bi-building-gear'),
    'reports': ('case_reports', 'bi-clipboard-data'),
    'attendance': ('my_attendance', 'bi-person-check'),
    'gps_tracking': ('gps_dashboard', 'bi-geo-alt'),
    'daily_meeting': ('dom_dashboard', 'bi-people-fill'),
    'hr': ('erms_dashboard', 'bi-inbox'),
}


def populate_menu_url_names(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    sort = 10
    for codename, (url_name, icon) in PERMISSION_MENU_MAP.items():
        updated = ModulePermission.objects.filter(codename=codename).update(
            menu_url_name=url_name,
            menu_icon=icon,
            sort_order=sort,
        )
        if updated:
            sort += 10


def reverse_populate(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    ModulePermission.objects.filter(codename__in=PERMISSION_MENU_MAP).update(
        menu_url_name='',
        menu_icon='bi-circle',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_enterprise_user_management_phase1'),
    ]

    operations = [
        migrations.RunPython(populate_menu_url_names, reverse_populate),
    ]
