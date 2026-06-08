from django.urls import path
from . import views

urlpatterns = [
    path('', views.control_panel, name='document_control_panel'),
    path('settings/', views.document_settings, name='document_settings'),
]
