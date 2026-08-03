from django.urls import path

from . import views

urlpatterns = [
    path('', views.project_list, name='special_project_list'),
    path('from-order/<int:order_id>/', views.open_from_order, name='special_project_open_from_order'),
    path('<int:pk>/', views.project_detail, name='special_project_detail'),
    path('<int:pk>/edit/', views.project_edit, name='special_project_edit'),
    path('<int:pk>/complete/', views.mark_project_completed, name='special_project_complete'),
    path('<int:project_pk>/daily-logs/add/', views.daily_log_create, name='special_project_daily_log_create'),
    path('daily-logs/<int:pk>/', views.daily_log_detail, name='special_project_daily_log_detail'),
    path('daily-logs/<int:pk>/edit/', views.daily_log_edit, name='special_project_daily_log_edit'),
]
