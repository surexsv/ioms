from django.urls import path
from . import views

urlpatterns = [
    path('', views.stuck_dashboard, name='case_stuck_dashboard'),
    path('search/', views.case_search, name='case_search'),
    path('search/api/', views.case_search_api, name='case_search_api'),
    path('tracker/', views.case_tracker, name='case_tracker'),
    path('activities/', views.activity_log, name='case_activity_log'),
    path('reports/', views.reports, name='case_reports'),
    path('export/stuck.csv', views.export_stuck_csv, name='case_export_stuck_csv'),
    path('export/aging.csv', views.export_aging_csv, name='case_export_aging_csv'),
]
