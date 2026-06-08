from django.db import migrations, models


def populate_order_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.order_by('order_id'):
        order.order_no = f"INF-ORD-2026-{order.order_id:04d}"
        order.save(update_fields=['order_no'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='order_no',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.RunPython(populate_order_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='order_no',
            field=models.CharField(blank=True, max_length=30, unique=True),
        ),
    ]
