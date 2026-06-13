from django.urls import path
from . import views

urlpatterns = [
    path('', views.wcr_list, name='wcr_list'),
    path('create/', views.create_wcr, name='create_wcr'),
    path('survey/<int:schedule_pk>/', views.create_survey_wcr, name='create_survey_wcr'),
    path('schedule-team/<int:order_id>/', views.schedule_team_json, name='wcr_schedule_team'),
    path('<int:pk>/approve/', views.approve_wcr, name='approve_wcr'),
]
