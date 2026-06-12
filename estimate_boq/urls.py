from django.urls import path
from . import views

urlpatterns = [
    path('', views.estimate_boq_list, name='estimate_boq_list'),
    path('create/', views.create_estimate_boq, name='create_estimate_boq'),
    path('<int:pk>/', views.estimate_boq_detail, name='estimate_boq_detail'),
    path('<int:pk>/edit/', views.edit_estimate_boq, name='edit_estimate_boq'),
]
