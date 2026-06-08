from django.urls import path
from . import views

urlpatterns = [
    path('', views.company_settings_view, name='company_settings'),
]
