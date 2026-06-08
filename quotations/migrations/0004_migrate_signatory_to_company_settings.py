from django.db import migrations


def copy_signatory_to_company_settings(apps, schema_editor):
    CoveringLetterSettings = apps.get_model('quotations', 'CoveringLetterSettings')
    CompanySettings = apps.get_model('company_settings', 'CompanySettings')

    cl = CoveringLetterSettings.objects.filter(pk=1).first()
    cs, _ = CompanySettings.objects.get_or_create(pk=1)
    if not cl:
        return

    if cl.signatory_name and not cs.authorized_signatory_name:
        cs.authorized_signatory_name = cl.signatory_name
    legacy_label = cl.designation.strip().lower() if cl.designation else ''
    if cl.designation and legacy_label not in ('authorized signatory', 'authorised signatory'):
        if not cs.authorized_signatory_designation:
            cs.authorized_signatory_designation = cl.designation
    elif not cs.authorized_signatory_designation:
        cs.authorized_signatory_designation = 'Director'
    if cl.signature_image and not cs.signature_image:
        cs.signature_image = cl.signature_image
    if cl.company_seal and not cs.company_seal:
        cs.company_seal = cl.company_seal
    cs.save()


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0001_initial'),
        ('quotations', '0003_covering_letter_and_templates'),
    ]

    operations = [
        migrations.RunPython(copy_signatory_to_company_settings, migrations.RunPython.noop),
    ]
