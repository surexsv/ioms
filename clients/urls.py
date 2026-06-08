from django.urls import path
from . import views

urlpatterns = [
    path('', views.client_list, name='client_list'),
    path('create/', views.create_client, name='create_client'),
    path('<int:pk>/edit/', views.edit_client, name='edit_client'),
]
