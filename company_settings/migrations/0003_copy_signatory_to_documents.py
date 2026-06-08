from django.db import migrations


def copy_company_signatory_to_documents(apps, schema_editor):
    CompanySettings = apps.get_model('company_settings', 'CompanySettings')
    Quotation = apps.get_model('quotations', 'Quotation')
    Invoice = apps.get_model('billing', 'Invoice')

    cs = CompanySettings.objects.filter(pk=1).first()
    if not cs:
        return

    name = (cs.authorized_signatory_name or '').strip()
    designation = (cs.authorized_signatory_designation or '').strip()
    if designation.lower() in ('authorized signatory', 'authorised signatory'):
        designation = ''

    for model in (Quotation, Invoice):
        for obj in model.objects.all():
            updated = False
            if name and not (obj.authorized_signatory_name or '').strip():
                obj.authorized_signatory_name = name
                updated = True
            if designation and not (obj.authorized_signatory_designation or '').strip():
                obj.authorized_signatory_designation = designation
                updated = True
            if cs.signature_image and not obj.signature_image:
                obj.signature_image = cs.signature_image
                updated = True
            if updated:
                obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0002_fix_legacy_signatory_designation'),
        ('quotations', '0006_quotation_authorized_signatory_designation_and_more'),
        ('billing', '0006_invoice_authorized_signatory_designation_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_company_signatory_to_documents, migrations.RunPython.noop),
    ]
