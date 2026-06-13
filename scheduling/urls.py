from django.urls import path
from . import views

urlpatterns = [
    path('', views.schedule_list, name='schedule_list'),
    path('calendar/', views.schedule_calendar, name='schedule_calendar'),
    path('create/<int:order_pk>/', views.schedule_create, name='schedule_create'),
    path('<int:pk>/edit/', views.schedule_edit, name='schedule_edit'),
]
