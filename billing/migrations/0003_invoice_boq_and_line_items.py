import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('boq', '0001_initial'),
        ('billing', '0002_invoice_extra_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='boq',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'status': 'VERIFIED'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='invoices',
                to='boq.boq',
            ),
        ),
        migrations.CreateModel(
            name='InvoiceLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sl_no', models.PositiveIntegerField()),
                ('description', models.TextField(verbose_name='Item / Service Description')),
                ('hsn_sac', models.CharField(max_length=20, verbose_name='HSN / SAC code')),
                ('unit', models.CharField(default='Nos', max_length=20)),
                ('qty', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('rate', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('remarks', models.CharField(blank=True, max_length=255)),
                ('from_boq', models.BooleanField(default=False, help_text='Line copied from verified BOQ')),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='billing.invoice')),
            ],
            options={
                'ordering': ['sl_no'],
            },
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='hsn_sac',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='quantity',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='unit',
        ),
    ]
