from django.urls import path
from django.views.generic import RedirectView
from .views import (
    OMSLoginView,
    OMSLogoutView,
    home,
    logout_success,
    access_denied,
    register,
    profile_resubmit,
    account_status,
    user_approval_list,
    user_approval_detail,
    user_approve,
    user_reject,
)

urlpatterns = [
    path('', home, name='home'),
    path('login/', OMSLoginView.as_view(), name='login'),
    path('login', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('logout/', OMSLogoutView.as_view(), name='logout'),
    path('logged-out/', logout_success, name='logout_success'),
    path('access-denied/', access_denied, name='access_denied'),
    path('register/', register, name='register'),
    path('profile-resubmit/', profile_resubmit, name='profile_resubmit'),
    path('account-status/', account_status, name='account_status'),
    path('user-approvals/', user_approval_list, name='user_approval_list'),
    path('user-approvals/<int:pk>/', user_approval_detail, name='user_approval_detail'),
    path('user-approvals/<int:pk>/approve/', user_approve, name='user_approve'),
    path('user-approvals/<int:pk>/reject/', user_reject, name='user_reject'),
]
