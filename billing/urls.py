from django.urls import path
from . import views, views_import

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('create/', views.create_invoice, name='create_invoice'),
    path('import/', views_import.invoice_import_upload, name='invoice_import_upload'),
    path('import/template/', views_import.invoice_import_template, name='invoice_import_template'),
    path('import/history/', views_import.invoice_import_history, name='invoice_import_history'),
    path('import/<int:pk>/', views_import.invoice_import_preview, name='invoice_import_preview'),
    path('import/<int:pk>/item/<int:item_id>/', views_import.invoice_import_item, name='invoice_import_item'),
    path('import/<int:pk>/confirm/', views_import.invoice_import_confirm, name='invoice_import_confirm'),
    path('import/<int:pk>/pdfs/', views_import.invoice_import_pdfs, name='invoice_import_pdfs'),
    path('boq-lines/<int:boq_id>/', views.boq_lines_json, name='boq_lines_json'),
    path('order-gst/<int:order_id>/', views.order_gst_json, name='order_gst_json'),
    path('<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('<int:pk>/edit/', views.edit_invoice, name='edit_invoice'),
    path('<int:pk>/unlock/', views.unlock_invoice_view, name='unlock_invoice'),
    path('<int:pk>/submit/', views.submit_invoice_view, name='submit_invoice'),
    path('<int:pk>/approve/', views.approve_invoice_view, name='approve_invoice'),
    path('<int:pk>/reject/', views.reject_invoice_view, name='reject_invoice'),
    path('<int:pk>/pay/', views.mark_paid, name='mark_paid'),
    path('<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
]
