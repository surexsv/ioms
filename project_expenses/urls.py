from django.urls import path

from . import views

urlpatterns = [
    path('', views.peams_dashboard, name='peams_dashboard'),
    path('categories/', views.category_list, name='peams_category_list'),
    path('categories/add/', views.category_create, name='peams_category_create'),
    path('settings/', views.settings_view, name='peams_settings'),
    path('advances/', views.advance_list, name='peams_advance_list'),
    path('advances/add/', views.advance_create, name='peams_advance_create'),
    path('advances/<int:pk>/', views.advance_detail, name='peams_advance_detail'),
    path('expenses/', views.expense_list, name='peams_expense_list'),
    path('expenses/add/', views.expense_create, name='peams_expense_create'),
    path('expenses/<int:pk>/', views.expense_detail, name='peams_expense_detail'),
    path('approvals/', views.pending_approvals, name='peams_pending_approvals'),
    path('ledger/employee/', views.employee_ledger, name='peams_employee_ledger'),
    path('ledger/project/', views.project_ledger, name='peams_project_ledger'),
]
