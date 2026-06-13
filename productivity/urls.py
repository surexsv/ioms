from django.urls import path
from . import views

urlpatterns = [
    path('', views.productivity_dashboard, name='productivity_dashboard'),
    path('employee/<int:pk>/', views.employee_productivity, name='employee_productivity'),
    path('activities/', views.activity_list, name='productivity_activities'),
    path('field-activities/', views.field_activity_list, name='field_activity_list'),
    path('gps/', views.gps_dashboard, name='gps_dashboard'),
    path('site-checkin/<int:schedule_pk>/', views.site_check_in_view, name='site_check_in'),
    path('site-checkout/<int:schedule_pk>/', views.site_check_out_view, name='site_check_out'),
    path('export/csv/', views.export_csv, name='productivity_export_csv'),
    path('export/pdf/', views.export_pdf, name='productivity_export_pdf'),
    path('export/field-csv/', views.export_field_csv, name='field_export_csv'),
]
