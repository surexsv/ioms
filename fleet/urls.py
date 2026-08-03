from django.urls import path

from . import views

urlpatterns = [
    path('', views.fleet_dashboard, name='fleet_dashboard'),
    path('vehicles/', views.vehicle_list, name='fleet_vehicle_list'),
    path('vehicles/add/', views.vehicle_create, name='fleet_vehicle_create'),
    path('vehicles/<int:pk>/edit/', views.vehicle_edit, name='fleet_vehicle_edit'),
    path('cards/', views.card_list, name='fleet_card_list'),
    path('cards/add/', views.card_create, name='fleet_card_create'),
    path('cards/<int:pk>/', views.card_detail, name='fleet_card_detail'),
    path('cards/<int:pk>/recharge/', views.card_recharge, name='fleet_card_recharge'),
    path('fuel/', views.fuel_list, name='fleet_fuel_list'),
    path('fuel/add/', views.fuel_create, name='fleet_fuel_create'),
    path('fuel/<int:pk>/', views.fuel_detail, name='fleet_fuel_detail'),
    path('fuel/<int:pk>/edit/', views.fuel_edit, name='fleet_fuel_edit'),
    path('reimbursements/', views.reimbursement_list, name='fleet_reimbursement_list'),
    path('reimbursements/<int:pk>/update/', views.reimbursement_update, name='fleet_reimbursement_update'),
    path('petty-cash/', views.petty_cash, name='fleet_petty_cash'),
    path('mileage/', views.mileage_report, name='fleet_mileage_report'),
]
