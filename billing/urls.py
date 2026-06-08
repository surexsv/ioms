from django.urls import path
from . import views

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('create/', views.create_invoice, name='create_invoice'),
    path('boq-lines/<int:boq_id>/', views.boq_lines_json, name='boq_lines_json'),
    path('<int:pk>/pay/', views.mark_paid, name='mark_paid'),
    path('<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
]
