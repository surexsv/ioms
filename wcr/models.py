
from django.db import models
from orders.models import Order
from django.conf import settings

from company_settings.mixins import AuthorizedSignatoryMixin
from productivity.constants import COMPLETION_STATUS_CHOICES, COMPLETION_COMPLETED


class WorkCompletionReport(AuthorizedSignatoryMixin, models.Model):

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    schedule = models.ForeignKey(
        'scheduling.WorkSchedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wcrs',
    )
    wcr_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    work_description = models.TextField()
    material_used = models.TextField(blank=True)
    photo = models.ImageField(upload_to='wcr_photos/', blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    submitted_date = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    work_start_time = models.DateTimeField(null=True, blank=True)
    work_end_time = models.DateTimeField(null=True, blank=True)
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    completion_status = models.CharField(
        max_length=15,
        choices=COMPLETION_STATUS_CHOICES,
        default=COMPLETION_COMPLETED,
    )

    def __str__(self):
        return self.wcr_number or f"WCR for Order {self.order.order_id}"

    def save(self, *args, **kwargs):
        if not self.wcr_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_WCR
            self.wcr_number = generate_document_number(DOC_WCR)
        if self.work_start_time and self.work_end_time and not self.total_hours:
            from productivity.calculator import compute_hours_from_times
            self.total_hours = compute_hours_from_times(self.work_start_time, self.work_end_time)
        super().save(*args, **kwargs)
        if self.approved:
            self.order.status = 'APPROVED'
        else:
            self.order.status = 'WCR_SUBMITTED'
        self.order.save(update_fields=['status'])
