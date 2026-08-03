from django.contrib import admin

from .models import Order, OrderAttachment


class OrderAttachmentInline(admin.TabularInline):
    model = OrderAttachment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_no', 'order_id', 'client', 'order_type', 'source', 'status',
        'order_date', 'expected_completion_date',
    )
    list_filter = ('status', 'order_type', 'source')
    search_fields = ('order_no', 'client__name', 'project_site_name')
    inlines = [OrderAttachmentInline]
