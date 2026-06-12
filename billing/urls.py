from django.urls import path
from . import views

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('create/', views.create_invoice, name='create_invoice'),
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
