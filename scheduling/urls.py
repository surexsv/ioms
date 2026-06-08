from django.urls import path
from . import views

urlpatterns = [
    path('create/<int:order_pk>/', views.schedule_create, name='schedule_create'),
    path('<int:pk>/edit/', views.schedule_edit, name='schedule_edit'),
]
