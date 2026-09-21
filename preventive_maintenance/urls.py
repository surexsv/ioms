from django.urls import path

from . import views

urlpatterns = [
    path('', views.pm_dashboard, name='pm_dashboard'),
    path('observations/', views.pm_observation_list, name='pm_observation_list'),
    path('observations/create/', views.pm_observation_create, name='pm_observation_create'),
    path('observations/<int:pk>/', views.pm_observation_detail, name='pm_observation_detail'),
]
