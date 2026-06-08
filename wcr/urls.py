from django.urls import path
from . import views

urlpatterns = [
    path('', views.wcr_list, name='wcr_list'),
    path('create/', views.create_wcr, name='create_wcr'),
    path('<int:pk>/approve/', views.approve_wcr, name='approve_wcr'),
]
