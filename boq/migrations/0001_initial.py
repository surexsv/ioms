import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0002_order_order_no'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BOQ',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('boq_number', models.CharField(blank=True, max_length=30, unique=True)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('VERIFIED', 'Verified')], default='DRAFT', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='boqs_created', to=settings.AUTH_USER_MODEL)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='boqs', to='orders.order')),
                ('verified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='boqs_verified', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'BOQ',
                'verbose_name_plural': 'BOQs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BOQLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sl_no', models.PositiveIntegerField()),
                ('description', models.TextField(verbose_name='Item / Service Description')),
                ('hsn_sac', models.CharField(max_length=20, verbose_name='HSN / SAC code')),
                ('unit', models.CharField(default='Nos', max_length=20)),
                ('qty', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('boq', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='boq.boq')),
            ],
            options={
                'ordering': ['sl_no'],
                'unique_together': {('boq', 'sl_no')},
            },
        ),
    ]
