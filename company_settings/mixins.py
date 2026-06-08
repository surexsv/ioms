from django.db import models


class AuthorizedSignatoryMixin(models.Model):
    """
    Reusable per-document authorized signatory fields.
    Attach to any IOMS document model (quotations, invoices, WCR, BOQ, etc.).
    """

    authorized_signatory_name = models.CharField(max_length=100, blank=True, null=True)
    authorized_signatory_designation = models.CharField(max_length=100, blank=True, null=True)
    signature_image = models.ImageField(upload_to='signatures/', blank=True, null=True)

    class Meta:
        abstract = True
