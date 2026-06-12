from decimal import Decimal

from django.db import migrations


def backfill_invoices(apps, schema_editor):
    Invoice = apps.get_model('billing', 'Invoice')
    from billing.gst import calculate_gst_breakdown, resolve_client_gst_type

    for invoice in Invoice.objects.select_related('order', 'order__client').all():
        client = invoice.order.client
        gst_type = resolve_client_gst_type(client)
        breakdown = calculate_gst_breakdown(invoice.amount or Decimal('0'), gst_type)
        invoice.gst_type = breakdown['gst_type']
        invoice.cgst_amount = breakdown['cgst_amount']
        invoice.sgst_amount = breakdown['sgst_amount']
        invoice.igst_amount = breakdown['igst_amount']
        invoice.save(update_fields=[
            'gst_type', 'cgst_amount', 'sgst_amount', 'igst_amount',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_invoice_cgst_amount_invoice_gst_type_and_more'),
        ('clients', '0003_sync_client_gst_data'),
    ]

    operations = [
        migrations.RunPython(backfill_invoices, migrations.RunPython.noop),
    ]
