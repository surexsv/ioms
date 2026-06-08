from django.conf import settings as django_settings
from django.db import models


class CompanySettings(models.Model):
    """
    Company-wide assets shared across documents (e.g. company seal).
    Per-document signatory details live on each document model.
    """

    company_seal = models.ImageField(
        upload_to='company/seals/',
        blank=True,
        null=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='company_settings_updates',
    )

    class Meta:
        verbose_name = 'Company settings'
        verbose_name_plural = 'Company settings'

    def __str__(self):
        return 'Company Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
