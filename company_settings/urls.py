from django.urls import path
from . import views

urlpatterns = [
    path('', views.company_settings_view, name='company_settings'),
    path('field-operations/', views.field_operations_settings_view, name='field_operations_settings'),
]
