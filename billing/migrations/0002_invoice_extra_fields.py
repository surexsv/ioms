from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='hsn_sac',
            field=models.CharField(blank=True, default='998422', max_length=20),
        ),
        migrations.AddField(
            model_name='invoice',
            name='po_date',
            field=models.DateField(blank=True, null=True, verbose_name='PO Date'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='po_number',
            field=models.CharField(blank=True, max_length=50, verbose_name='PO/SO No'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='quantity',
            field=models.DecimalField(decimal_places=2, default=1, max_digits=10),
        ),
        migrations.AddField(
            model_name='invoice',
            name='service_title',
            field=models.CharField(
                blank=True,
                help_text='e.g. OFC Connectivity — shown above client name on invoice',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='unit',
            field=models.CharField(default='Nos', max_length=20),
        ),
    ]
