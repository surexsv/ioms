from django.conf import settings
from django.db import models


class OrderVoiceNote(models.Model):
    """A confirmed field note: the Malayalam that was spoken, and the English that was saved."""

    KIND_UPDATE = 'UPDATE'
    KIND_COMPLETION = 'COMPLETION'
    KIND_CLOSING = 'CLOSING'
    KIND_CHOICES = (
        (KIND_UPDATE, 'Order Update'),
        (KIND_COMPLETION, 'Work Completion'),
        (KIND_CLOSING, 'Closing Remarks'),
    )

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='voice_notes',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    malayalam_text = models.TextField()
    english_text = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_voice_notes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_kind_display()} on order {self.order_id}'
