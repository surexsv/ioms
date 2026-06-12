from django.urls import path
from . import views

urlpatterns = [
    path('', views.enquiry_list, name='enquiry_list'),
    path('create/', views.create_enquiry, name='create_enquiry'),
    path('<int:pk>/', views.enquiry_detail, name='enquiry_detail'),
    path('<int:pk>/edit/', views.edit_enquiry, name='edit_enquiry'),
    path('<int:pk>/convert/', views.convert_enquiry_order, name='convert_enquiry_order'),
    path('site-progress/create/', views.site_progress_create, name='site_progress_create'),
]
