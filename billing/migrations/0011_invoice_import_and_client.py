from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import billing.models


def backfill_invoice_client(apps, schema_editor):
    Invoice = apps.get_model('billing', 'Invoice')
    for invoice in Invoice.objects.select_related('order').all():
        if invoice.order_id and not invoice.client_id:
            invoice.client_id = invoice.order.client_id
            invoice.save(update_fields=['client_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0010_alter_invoiceapprovalauditlog_action'),
        ('clients', '0005_alter_client_gst_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='order',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='invoice',
                to='orders.order',
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='client',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='invoices',
                to='clients.client',
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='source',
            field=models.CharField(
                choices=[('ORDER', 'Order workflow'), ('IMPORT', 'Manual import')],
                db_index=True,
                default='ORDER',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='billing_period_from',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='billing_period_to',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='invoice_date',
            field=models.DateField(default=billing.models.default_invoice_date),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='due_date',
            field=models.DateField(default=billing.models.default_invoice_due_date),
        ),
        migrations.CreateModel(
            name='InvoiceImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=200)),
                ('original_filename', models.CharField(max_length=255)),
                ('file', models.FileField(blank=True, upload_to='billing_imports/%Y/%m/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(
                    choices=[
                        ('VALIDATED', 'Validated'),
                        ('CONFIRMED', 'Confirmed'),
                        ('CANCELLED', 'Cancelled'),
                        ('FAILED', 'Failed'),
                    ],
                    db_index=True,
                    default='VALIDATED',
                    max_length=15,
                )),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('invoice_count', models.PositiveIntegerField(default=0)),
                ('valid_count', models.PositiveIntegerField(default=0)),
                ('error_count', models.PositiveIntegerField(default=0)),
                ('warning_count', models.PositiveIntegerField(default=0)),
                ('skipped_count', models.PositiveIntegerField(default=0)),
                ('created_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('confirm_message', models.TextField(blank=True)),
                ('uploaded_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='invoice_import_batches',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.AddField(
            model_name='invoice',
            name='import_batch',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_invoices',
                to='billing.invoiceimportbatch',
            ),
        ),
        migrations.CreateModel(
            name='InvoiceImportItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('grouping_key', models.CharField(max_length=255)),
                ('invoice_number', models.CharField(blank=True, max_length=50)),
                ('number_mode', models.CharField(default='MANUAL', max_length=10)),
                ('payload', models.JSONField(default=dict)),
                ('status', models.CharField(
                    choices=[
                        ('VALID', 'Valid'),
                        ('WARNING', 'Warning'),
                        ('ERROR', 'Error'),
                        ('ALREADY_EXISTS', 'Already exists'),
                        ('CREATED', 'Created'),
                        ('FAILED', 'Failed'),
                        ('SKIPPED', 'Skipped'),
                    ],
                    default='VALID',
                    max_length=20,
                )),
                ('errors', models.JSONField(default=list)),
                ('warnings', models.JSONField(default=list)),
                ('batch', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='billing.invoiceimportbatch',
                )),
                ('client', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='clients.client',
                )),
                ('created_invoice', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='import_items',
                    to='billing.invoice',
                )),
            ],
            options={
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.RunPython(backfill_invoice_client, noop),
    ]
