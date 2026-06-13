"""Case intelligence settings — configurable stuck-case thresholds."""

from django.conf import settings as django_settings
from django.db import models


class CaseIntelligenceSettings(models.Model):
    enquiry_delay_days = models.PositiveSmallIntegerField(
        default=7,
        verbose_name='Enquiry delay days',
        help_text='Flag enquiry if no activity for this many days.',
    )
    survey_delay_days = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Survey delay days',
        help_text='Days after scheduled survey date before flagging as delayed (0 = same day).',
    )
    quotation_followup_days = models.PositiveSmallIntegerField(
        default=15,
        verbose_name='Quotation follow-up days',
    )
    order_delay_days = models.PositiveSmallIntegerField(
        default=5,
        verbose_name='Order delay days',
        help_text='Flag order if no schedule created within this period.',
    )
    wcr_delay_days = models.PositiveSmallIntegerField(
        default=3,
        verbose_name='WCR delay days',
        help_text='Flag completed order if WCR not submitted within this period.',
    )
    invoice_approval_days = models.PositiveSmallIntegerField(
        default=3,
        verbose_name='Invoice approval days',
        help_text='Flag submitted invoice pending approval beyond this many days.',
    )
    payment_followup_days = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Payment follow-up days',
        help_text='Days after due date before flagging payment follow-up (0 = on due date).',
    )
    # Legacy field names kept for backward-compatible migrations
    enquiry_inactive_days = models.PositiveSmallIntegerField(default=7, editable=False)
    order_schedule_delay_days = models.PositiveSmallIntegerField(default=5, editable=False)
    wcr_submit_delay_days = models.PositiveSmallIntegerField(default=3, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='case_intel_settings_updates',
    )

    class Meta:
        verbose_name = 'Case intelligence settings'
        verbose_name_plural = 'Case intelligence settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        # Keep legacy columns in sync for any code still reading old names
        self.enquiry_inactive_days = self.enquiry_delay_days
        self.order_schedule_delay_days = self.order_delay_days
        self.wcr_submit_delay_days = self.wcr_delay_days
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def get_case_settings():
    return CaseIntelligenceSettings.get_solo()
