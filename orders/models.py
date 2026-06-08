
from django.db import models
from django.conf import settings
from clients.models import Client
from django.utils import timezone


class Order(models.Model):

    ORDER_TYPE = (
        ('SURVEY', 'Survey'),
        ('INSTALLATION', 'Installation'),
        ('COMPLAINT', 'Complaint'),
        ('MAINTENANCE', 'Maintenance'),
    )

    STATUS_CHOICES = (
        ('NEW', 'New'),
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('WCR_SUBMITTED', 'WCR Submitted'),
        ('APPROVED', 'Approved'),
        ('BILLED', 'Billed'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('CLOSED', 'Closed'),
    )

    order_id = models.AutoField(primary_key=True)
    order_no = models.CharField(max_length=30, unique=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    order_date = models.DateField(default=timezone.now)
    project_site_name = models.CharField(max_length=200, blank=True)
    site_address = models.TextField(verbose_name='Location')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE)
    description = models.TextField()
    priority = models.CharField(max_length=20, default='Normal')
    expected_completion_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    target_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='legacy_assigned_orders',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')

    def save(self, *args, **kwargs):
        if not self.order_no:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_ORDER
            self.order_no = generate_document_number(DOC_ORDER)
        if not self.expected_completion_date and self.target_date:
            self.expected_completion_date = self.target_date
        super().save(*args, **kwargs)

    def __str__(self):
        label = self.order_no or f"#{self.order_id}"
        return f"Order {label} - {self.client.name}"

    @property
    def display_site_name(self):
        return self.project_site_name or self.client.name

    @property
    def has_schedule(self):
        return hasattr(self, 'work_schedule')

    def update_status(self, new_status):
        allowed_transitions = {
            'NEW': ['SCHEDULED'],
            'SCHEDULED': ['IN_PROGRESS'],
            'IN_PROGRESS': ['COMPLETED'],
            'COMPLETED': ['WCR_SUBMITTED'],
            'WCR_SUBMITTED': ['APPROVED'],
            'APPROVED': ['BILLED'],
            'BILLED': ['PAYMENT_PENDING'],
            'PAYMENT_PENDING': ['CLOSED'],
        }
        if new_status in allowed_transitions.get(self.status, []):
            self.status = new_status
            self.save()
            return True
        return False


class OrderAttachment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='order_attachments/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.caption or self.file.name
