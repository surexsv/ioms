from django.urls import path
from . import views

urlpatterns = [
    path('', views.boq_list, name='boq_list'),
    path('create/', views.create_boq, name='create_boq'),
    path('<int:pk>/', views.boq_detail, name='boq_detail'),
    path('<int:pk>/edit/', views.edit_boq, name='edit_boq'),
    path('<int:pk>/verify/', views.verify_boq, name='verify_boq'),
]
