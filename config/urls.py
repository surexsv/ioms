from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('accounts.urls')),
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path('orders/', include('orders.urls')),
    path('clients/', include('clients.urls')),
    path('wcr/', include('wcr.urls')),
    path('billing/', include('billing.urls')),
    path('boq/', include('boq.urls')),
    path('quotations/', include('quotations.urls')),
    path('attendance/', include('attendance.urls')),
    path('document-generator/', include('document_generator.urls')),
    path('company-settings/', include('company_settings.urls')),
    path('scheduling/', include('scheduling.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = 'accounts.error_handlers.permission_denied_view'
handler404 = 'accounts.error_handlers.page_not_found_view'
handler500 = 'accounts.error_handlers.server_error_view'
