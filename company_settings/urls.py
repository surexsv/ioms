from django.urls import path
from . import views

urlpatterns = [
    path('', views.company_settings_view, name='company_settings'),
    path('field-operations/', views.field_operations_settings_view, name='field_operations_settings'),
    path('case-intelligence/', views.case_intelligence_settings_view, name='case_intelligence_settings'),
]
