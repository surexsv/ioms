from django.urls import path

from . import views

urlpatterns = [
    path('', views.task_dashboard, name='task_dashboard'),
    path('list/', views.task_list, name='task_list'),
    path('create/', views.task_create, name='task_create'),
    path('history/', views.task_history, name='task_history'),
    path('<int:pk>/', views.task_detail, name='task_detail'),
]
