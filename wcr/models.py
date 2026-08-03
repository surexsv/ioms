from django.db import models
from orders.models import Order
from django.conf import settings

from company_settings.mixins import AuthorizedSignatoryMixin
from productivity.constants import COMPLETION_STATUS_CHOICES, COMPLETION_COMPLETED

WCR_TYPE_EXECUTION = 'EXECUTION'
WCR_TYPE_SURVEY = 'SURVEY'
WCR_TYPE_CHOICES = (
    (WCR_TYPE_EXECUTION, 'Execution WCR'),
    (WCR_TYPE_SURVEY, 'Survey WCR'),
)


class WorkCompletionReport(AuthorizedSignatoryMixin, models.Model):

    wcr_type = models.CharField(max_length=12, choices=WCR_TYPE_CHOICES, default=WCR_TYPE_EXECUTION)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, null=True, blank=True)
    enquiry = models.OneToOneField(
        'enquiries.Enquiry',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='survey_wcr',
    )
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
    site_findings = models.TextField(blank=True, verbose_name='Site Findings')
    feasibility_remarks = models.TextField(blank=True, verbose_name='Feasibility Remarks')

    def __str__(self):
        if self.wcr_type == WCR_TYPE_SURVEY and self.enquiry_id:
            return self.wcr_number or f'Survey WCR for {self.enquiry.enquiry_number}'
        return self.wcr_number or f"WCR for Order {self.order.order_id}"

    @property
    def is_survey_wcr(self):
        return self.wcr_type == WCR_TYPE_SURVEY

    def save(self, *args, **kwargs):
        if not self.wcr_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_WCR
            self.wcr_number = generate_document_number(DOC_WCR)
        if self.work_start_time and self.work_end_time and not self.total_hours:
            from productivity.calculator import compute_hours_from_times
            self.total_hours = compute_hours_from_times(self.work_start_time, self.work_end_time)
        super().save(*args, **kwargs)
        if self.wcr_type == WCR_TYPE_SURVEY or not self.order_id:
            return
        # Never regress billing/payment lifecycle statuses on WCR re-save
        if self.order.status in ('BILLED', 'PAYMENT_PENDING', 'CLOSED'):
            return
        new_status = 'APPROVED' if self.approved else 'WCR_SUBMITTED'
        if self.order.status != new_status:
            self.order.status = new_status
            self.order.save(update_fields=['status'])
