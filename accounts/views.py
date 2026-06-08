from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from .access_control import pop_denial_context, REASON_UNAUTHORIZED
from .approval_services import approve_user, log_approval_action, mark_resubmitted, reject_user
from .decorators import access_denied_response, module_required
from .forms import (
    ApprovalAuthenticationForm,
    ProfileResubmitForm,
    ProfileResubmitVerifyForm,
    UserRegistrationForm,
    UserRejectionForm,
)
from .models import User, UserApprovalAuditLog
from .permissions import (
    allowed_dashboard_url_name,
    can_manage_user_approvals,
    MODULE_USER_APPROVAL,
)
from .security_log import log_access_denied
from .utils import dashboard_url_name_for_user


@method_decorator(never_cache, name='dispatch')
class OMSLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = ApprovalAuthenticationForm
    redirect_authenticated_user = False

    def get_success_url(self):
        user = self.request.user
        if not user.is_profile_approved:
            return reverse('account_status')
        return reverse(dashboard_url_name_for_user(user))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


@method_decorator(never_cache, name='dispatch')
class OMSLogoutView(LogoutView):
    http_method_names = ['post', 'options']
    next_page = 'logout_success'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


@never_cache
def logout_success(request):
    return render(request, 'accounts/logout_success.html')


@never_cache
def access_denied(request):
    if not request.user.is_authenticated:
        return redirect('login')

    denial = pop_denial_context(request)
    if not denial.get('attempted_url'):
        log_access_denied(request, reason=denial.get('reason', REASON_UNAUTHORIZED))

    referer = request.META.get('HTTP_REFERER', '')
    return render(
        request,
        'accounts/access_denied.html',
        {
            'page_title': denial['title'],
            'message': denial['message'],
            'reason': denial['reason'],
            'dashboard_url_name': allowed_dashboard_url_name(request.user),
            'go_back_url': referer,
            'show_go_back': bool(referer),
        },
        status=403,
    )


def home(request):
    if request.user.is_authenticated:
        if not request.user.is_profile_approved:
            return redirect('account_status')
        return redirect(dashboard_url_name_for_user(request.user))
    return redirect('login')


@never_cache
def register(request):
    if request.user.is_authenticated and request.user.is_profile_approved:
        return redirect(dashboard_url_name_for_user(request.user))

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            log_approval_action(
                user,
                UserApprovalAuditLog.ACTION_REGISTERED,
                performed_by=None,
                notes='Self-registration submitted.',
            )
            messages.success(
                request,
                'Registration submitted successfully. You will be notified once an administrator approves your profile.',
            )
            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@never_cache
def profile_resubmit(request):
    user = None
    verify_form = ProfileResubmitVerifyForm()
    profile_form = None

    if request.method == 'POST':
        if 'verify' in request.POST:
            verify_form = ProfileResubmitVerifyForm(request.POST)
            if verify_form.is_valid():
                user = verify_form.cleaned_data['user']
                profile_form = ProfileResubmitForm(instance=user)
        elif 'resubmit' in request.POST:
            user_id = request.POST.get('user_id')
            user = get_object_or_404(User, pk=user_id, approval_status=User.APPROVAL_REJECTED)
            profile_form = ProfileResubmitForm(request.POST, request.FILES, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                mark_resubmitted(user)
                messages.success(
                    request,
                    'Your profile has been resubmitted and is pending administrator approval.',
                )
                return redirect('login')
    else:
        username = request.GET.get('username', '').strip()
        if username:
            verify_form = ProfileResubmitVerifyForm(initial={'username': username})

    audit_history = []
    if user:
        audit_history = user.approval_audit_logs.all()[:10]

    return render(request, 'accounts/profile_resubmit.html', {
        'verify_form': verify_form,
        'profile_form': profile_form,
        'user': user,
        'audit_history': audit_history,
    })


@login_required
@never_cache
def account_status(request):
    user = request.user
    if user.is_profile_approved:
        return redirect(dashboard_url_name_for_user(user))

    audit_history = user.approval_audit_logs.all()[:10]
    return render(request, 'accounts/account_status.html', {
        'user_obj': user,
        'audit_history': audit_history,
    })


@module_required(MODULE_USER_APPROVAL)
def user_approval_list(request):
    if not can_manage_user_approvals(request.user):
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    status_filter = request.GET.get('status', User.APPROVAL_PENDING)
    users = User.objects.exclude(is_superuser=True).order_by('-date_joined')
    if status_filter in dict(User.APPROVAL_STATUS_CHOICES):
        users = users.filter(approval_status=status_filter)

    return render(request, 'accounts/user_approval_list.html', {
        'users': users,
        'status_filter': status_filter,
        'status_choices': User.APPROVAL_STATUS_CHOICES,
    })


@module_required(MODULE_USER_APPROVAL)
def user_approval_detail(request, pk):
    if not can_manage_user_approvals(request.user):
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    user = get_object_or_404(User, pk=pk)
    audit_history = user.approval_audit_logs.all()
    return render(request, 'accounts/user_approval_detail.html', {
        'profile_user': user,
        'audit_history': audit_history,
    })


@module_required(MODULE_USER_APPROVAL)
def user_approve(request, pk):
    if not can_manage_user_approvals(request.user):
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        approve_user(user, request.user)
        messages.success(request, 'User approved successfully.')
        return redirect('user_approval_list')
    return redirect('user_approval_detail', pk=pk)


@module_required(MODULE_USER_APPROVAL)
def user_reject(request, pk):
    if not can_manage_user_approvals(request.user):
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserRejectionForm(request.POST)
        if form.is_valid():
            reject_user(user, request.user, form.cleaned_data['rejection_reason'])
            messages.success(request, 'User registration rejected.')
            return redirect('user_approval_list')
    else:
        form = UserRejectionForm()

    return render(request, 'accounts/user_reject.html', {
        'form': form,
        'profile_user': user,
    })
