from django.db import models

from billing.gst import (
    GST_TYPE_CHOICES,
    INDIAN_STATE_CHOICES,
    resolve_client_gst_type,
    resolve_client_state_display,
    gst_type_label,
    sync_client_gst_fields,
)


class Client(models.Model):

    COMPANY_TYPE = (
        ('TELECOM', 'Telecom'),
        ('IT', 'IT Infrastructure'),
        ('CCTV', 'CCTV'),
        ('NETWORK', 'Networking'),
        ('WIFI', 'WiFi'),
    )

    name = models.CharField(max_length=200)
    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE)
    gst_number = models.CharField(max_length=20, blank=True, verbose_name='GST Number')
    pan_number = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='PAN Number',
        help_text='10-character PAN; auto-filled from GSTIN when possible',
    )
    state = models.CharField(
        max_length=50,
        blank=True,
        choices=[('', '— Select State —')] + [(s, s) for s in INDIAN_STATE_CHOICES],
        help_text='Client state for GST determination',
    )
    state_code = models.CharField(
        max_length=2,
        blank=True,
        verbose_name='State Code',
        help_text='GST state code (auto-filled from GSTIN when possible)',
    )
    gst_type = models.CharField(
        max_length=15,
        blank=True,
        choices=[('', 'Auto (from state)')] + list(GST_TYPE_CHOICES),
        verbose_name='GST Type',
        help_text='Leave blank to auto-apply CGST+SGST for Kerala, IGST for other states',
    )
    address = models.TextField()
    contact_person = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def resolved_gst_type(self):
        return resolve_client_gst_type(self)

    def resolved_gst_type_label(self):
        return gst_type_label(self.resolved_gst_type())

    def billing_state_display(self):
        return resolve_client_state_display(self)

    def sync_gst_metadata(self, save=False):
        return sync_client_gst_fields(self, save=save)
