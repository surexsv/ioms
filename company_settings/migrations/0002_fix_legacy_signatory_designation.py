from django.db import migrations


def fix_legacy_designation(apps, schema_editor):
    CompanySettings = apps.get_model('company_settings', 'CompanySettings')
    cs = CompanySettings.objects.filter(pk=1).first()
    if not cs:
        return
    designation = (cs.authorized_signatory_designation or '').strip().lower()
    if designation in ('authorized signatory', 'authorised signatory', ''):
        cs.authorized_signatory_designation = 'Director'
        cs.save(update_fields=['authorized_signatory_designation'])


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0001_initial'),
        ('quotations', '0005_remove_coveringlettersettings_company_seal_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_legacy_designation, migrations.RunPython.noop),
    ]
