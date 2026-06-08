from django.urls import path
from . import views

urlpatterns = [
    path('', views.attendance_dashboard, name='attendance_dashboard'),
    path('list/', views.attendance_list, name='attendance_list'),
    path('create/', views.attendance_create, name='attendance_create'),
    path('<int:pk>/edit/', views.attendance_edit, name='attendance_edit'),
    path('my/', views.my_attendance, name='my_attendance'),
    path('check-in/', views.check_in, name='attendance_check_in'),
    path('check-out/', views.check_out, name='attendance_check_out'),
    path('reports/daily/', views.report_daily, name='attendance_report_daily'),
    path('reports/monthly/', views.report_monthly, name='attendance_report_monthly'),
    path('reports/employee/', views.report_employee, name='attendance_report_employee'),
]
