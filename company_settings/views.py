from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.access_control import REASON_ROLE
from accounts.decorators import access_denied_response, module_required
from accounts.permissions import MODULE_COMPANY_SETTINGS

from .forms import CompanySettingsForm
from .models import CompanySettings
from .permissions import can_manage_company_settings, can_view_company_settings


@login_required
@module_required(MODULE_COMPANY_SETTINGS)
def company_settings_view(request):
    if not can_view_company_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)

    settings_obj = CompanySettings.get_solo()
    can_edit = can_manage_company_settings(request.user)

    if request.method == 'POST':
        if not can_edit:
            return access_denied_response(request, reason=REASON_ROLE)
        form = CompanySettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Company settings updated.')
            return redirect('company_settings')
    else:
        form = CompanySettingsForm(instance=settings_obj)
        if not can_edit:
            for field in form.fields.values():
                field.disabled = True

    return render(request, 'company_settings/settings.html', {
        'form': form,
        'settings_obj': settings_obj,
        'can_edit': can_edit,
    })
