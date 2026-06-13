from django.conf import settings as django_settings
from django.db import models


class FieldOperationsSettings(models.Model):
    """Admin-configurable field operations features — no code changes required."""

    gps_tracking_enabled = models.BooleanField(
        default=True, verbose_name='GPS Tracking',
    )
    checkin_checkout_enabled = models.BooleanField(
        default=True, verbose_name='Site Check-In / Check-Out',
    )
    productivity_tracking_enabled = models.BooleanField(
        default=True, verbose_name='Productivity Tracking',
    )
    site_photos_enabled = models.BooleanField(
        default=True, verbose_name='Site Photo Uploads',
    )
    device_tracking_enabled = models.BooleanField(
        default=True, verbose_name='Device Information Tracking',
    )
    auto_survey_schedule_enabled = models.BooleanField(
        default=True, verbose_name='Auto-Create Survey Schedules',
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_ops_settings_updates',
    )

    class Meta:
        verbose_name = 'Field operations settings'
        verbose_name_plural = 'Field operations settings'

    def __str__(self):
        return 'Field Operations Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def is_gps_enabled():
    return FieldOperationsSettings.get_solo().gps_tracking_enabled


def is_checkin_enabled():
    return FieldOperationsSettings.get_solo().checkin_checkout_enabled


def is_productivity_enabled():
    return FieldOperationsSettings.get_solo().productivity_tracking_enabled


def is_site_photos_enabled():
    return FieldOperationsSettings.get_solo().site_photos_enabled


def is_auto_survey_schedule_enabled():
    return FieldOperationsSettings.get_solo().auto_survey_schedule_enabled
