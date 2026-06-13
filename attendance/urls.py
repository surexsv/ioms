from django.urls import path
from . import views

urlpatterns = [
    path('', views.attendance_dashboard, name='attendance_dashboard'),
    path('list/', views.attendance_list, name='attendance_list'),
    path('create/', views.attendance_create, name='attendance_create'),
    path('photos/<int:pk>/', views.attendance_photo, name='attendance_photo'),
    path('<int:pk>/', views.attendance_detail, name='attendance_detail'),
    path('<int:pk>/edit/', views.attendance_edit, name='attendance_edit'),
    path('my/', views.my_attendance, name='my_attendance'),
    path('check-in/', views.check_in, name='attendance_check_in'),
    path('check-out/', views.check_out, name='attendance_check_out'),
    path('team/', views.team_attendance, name='attendance_team'),
    path('reports/', views.reports_index, name='attendance_reports'),
    path('reports/daily/', views.report_daily, name='attendance_report_daily'),
    path('reports/monthly/', views.report_monthly, name='attendance_report_monthly'),
    path('reports/employee/', views.report_employee, name='attendance_report_employee'),
    path('reports/absent/', views.report_absent, name='attendance_report_absent'),
    path('reports/late/', views.report_late, name='attendance_report_late'),
    path('reports/leave/', views.report_leave, name='attendance_report_leave'),
    path('reports/department/', views.report_department, name='attendance_report_department'),
    path('reports/location/', views.report_location, name='attendance_report_location'),
    path('reports/photo/', views.report_photo, name='attendance_report_photo'),
]
