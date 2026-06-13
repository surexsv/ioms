from django.urls import path
from . import views

urlpatterns = [
    path('', views.director_dashboard, name='director_dashboard'),
    path('operations/', views.operations_dashboard, name='operations_dashboard'),
    path('accounts/', views.accounts_dashboard, name='accounts_dashboard'),
    path('field-team/', views.field_team_dashboard, name='field_team_dashboard'),
    path('engineer/', views.engineer_dashboard, name='engineer_dashboard'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('project-manager/', views.project_manager_dashboard, name='project_manager_dashboard'),
]
