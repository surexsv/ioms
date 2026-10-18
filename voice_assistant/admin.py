from django.contrib import admin

from .models import OrderVoiceNote


@admin.register(OrderVoiceNote)
class OrderVoiceNoteAdmin(admin.ModelAdmin):
    list_display = ('order', 'kind', 'created_by', 'created_at')
    list_filter = ('kind',)
    search_fields = ('malayalam_text', 'english_text', 'order__order_no')
