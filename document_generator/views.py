from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.access_control import REASON_ROLE
from accounts.decorators import login_required, module_required, access_denied_response
from accounts.permissions import MODULE_DOCUMENT_GENERATOR

from .forms import CounterResetForm, DocumentNumberSettingsForm
from .models import DocumentNumberSettings
from .permissions import can_manage_document_generator, can_view_document_generator
from .services import control_panel_rows, get_year_series, reset_counter, seed_counters_from_existing


@login_required
@module_required(MODULE_DOCUMENT_GENERATOR)
def control_panel(request):
    if not can_view_document_generator(request.user):
        return access_denied_response(request, reason=REASON_ROLE)

    rows = control_panel_rows()
    reset_form = CounterResetForm()
    can_manage = can_manage_document_generator(request.user)

    if request.method == 'POST' and can_manage:
        action = request.POST.get('action')
        if action == 'seed':
            seed_counters_from_existing()
            messages.success(request, 'Counters synchronized from existing document numbers.')
            return redirect('document_control_panel')
        if action == 'reset':
            reset_form = CounterResetForm(request.POST)
            if reset_form.is_valid():
                reset_counter(
                    reset_form.cleaned_data['document_type'],
                    user=request.user,
                )
                messages.success(request, 'Counter reset for the current year series.')
                return redirect('document_control_panel')

    return render(request, 'document_generator/control_panel.html', {
        'rows': rows,
        'year_series': get_year_series(),
        'can_manage': can_manage,
        'reset_form': reset_form,
    })


@login_required
@module_required(MODULE_DOCUMENT_GENERATOR)
def document_settings(request):
    if not can_view_document_generator(request.user):
        return access_denied_response(request, reason=REASON_ROLE)

    settings_obj = DocumentNumberSettings.get_solo()
    can_manage = can_manage_document_generator(request.user)

    if request.method == 'POST':
        if not can_manage or not settings_obj.allow_editing:
            return access_denied_response(request, reason=REASON_ROLE)
        form = DocumentNumberSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Document number settings updated.')
            return redirect('document_settings')
    else:
        form = DocumentNumberSettingsForm(instance=settings_obj)
        if not can_manage:
            for field in form.fields.values():
                field.disabled = True

    return render(request, 'document_generator/document_settings.html', {
        'form': form,
        'settings_obj': settings_obj,
        'can_manage': can_manage,
    })
