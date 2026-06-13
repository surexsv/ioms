from django.urls import path

from . import views

urlpatterns = [
    path('', views.erms_dashboard, name='erms_dashboard'),
    path('my/', views.erms_my_requests, name='erms_my_requests'),
    path('pending/', views.erms_pending_approvals, name='erms_pending_approvals'),
    path('create/', views.erms_request_create, name='erms_request_create'),
    path('notifications/', views.erms_notifications, name='erms_notifications'),
    path('notifications/read/', views.erms_notifications_read, name='erms_notifications_read'),
    path('reports/', views.erms_reports_index, name='erms_reports'),
    path('reports/register/', views.erms_report_register, name='erms_report_register'),
    path('reports/pending/', views.erms_report_pending, name='erms_report_pending'),
    path('reports/history/', views.erms_report_history, name='erms_report_history'),
    path('reports/department/', views.erms_report_department, name='erms_report_department'),
    path('reports/employee/', views.erms_report_employee, name='erms_report_employee'),
    path('reports/type/<str:codename>/', views.erms_report_type, name='erms_report_type'),
    path('<int:pk>/', views.erms_request_detail, name='erms_request_detail'),
    path('<int:pk>/edit/', views.erms_request_edit, name='erms_request_edit'),
    path('<int:pk>/submit/', views.erms_request_submit, name='erms_request_submit'),
    path('<int:pk>/approve/', views.erms_request_approve, name='erms_request_approve'),
    path('<int:pk>/reject/', views.erms_request_reject, name='erms_request_reject'),
    path('<int:pk>/return/', views.erms_request_return, name='erms_request_return'),
    path('<int:pk>/attach/', views.erms_attachment_upload, name='erms_attachment_upload'),
]
