# Generated manually for ERMS request numbering

from django.db import migrations, models

DOC_TYPE_CHOICES = [
    ('ORDER', 'Order'),
    ('QUOTATION', 'Quotation'),
    ('WCR', 'Work Completion Report'),
    ('BOQ', 'BOQ'),
    ('INVOICE', 'Invoice'),
    ('PURCHASE_ORDER', 'Purchase Order'),
    ('SCHEDULE', 'Work Schedule'),
    ('ENQUIRY', 'Enquiry'),
    ('ESTIMATE_BOQ', 'Estimate BOQ'),
    ('REQUEST', 'Employee Request'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('document_generator', '0003_documentnumbersettings_enquiry_prefix_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentnumbersettings',
            name='request_prefix',
            field=models.CharField(default='REQ', max_length=10),
        ),
        migrations.AlterField(
            model_name='documentcounter',
            name='document_type',
            field=models.CharField(choices=DOC_TYPE_CHOICES, max_length=20),
        ),
        migrations.AlterField(
            model_name='generateddocumentnumber',
            name='document_type',
            field=models.CharField(choices=DOC_TYPE_CHOICES, max_length=20),
        ),
    ]
