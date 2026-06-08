
from django.db import models
from orders.models import Order
from django.conf import settings

from company_settings.mixins import AuthorizedSignatoryMixin


class WorkCompletionReport(AuthorizedSignatoryMixin, models.Model):

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    wcr_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    work_description = models.TextField()
    material_used = models.TextField(blank=True)
    photo = models.ImageField(upload_to='wcr_photos/', blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    submitted_date = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.wcr_number or f"WCR for Order {self.order.order_id}"

    def save(self, *args, **kwargs):
        if not self.wcr_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_WCR
            self.wcr_number = generate_document_number(DOC_WCR)
        super().save(*args, **kwargs)
        if self.approved:
            self.order.status = 'APPROVED'
        else:
            self.order.status = 'WCR_SUBMITTED'
        self.order.save(update_fields=['status'])


# Create your models here.
