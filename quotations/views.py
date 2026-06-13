from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.access_control import REASON_ROLE
from accounts.decorators import module_required, role_required, access_denied_response
from accounts.permissions import (
    MODULE_QUOTATIONS,
    MODULE_QUOTATION_RATES,
    can_access,
)
from .forms import (
    QuotationForm,
    MaterialLineFormSet,
    ServiceLineFormSet,
    ServiceRateCardForm,
    MaterialRateCardForm,
    QuotationSearchForm,
    QuotationSettingsForm,
    CoveringLetterSettingsForm,
    ProposalTemplateForm,
)
from .models import (
    Quotation,
    QuotationSettings,
    CoveringLetterSettings,
    ProposalTemplate,
    ServiceRateCard,
    MaterialRateCard,
    RateCardAuditLog,
)
from .covering_letter_utils import body_to_paragraphs, paragraphs_to_body, covering_letter_context
from .permissions import (
    can_view_quotations,
    can_edit_quotations,
    can_approve_quotations,
    can_manage_rate_cards,
    can_view_quotation_settings,
    can_manage_quotation_settings,
)
from . import services
from .pdf import build_proposal_pdf
from .settings_utils import quotation_document_sections
from company_settings.permissions import can_edit_document_signatory


def _prepare_quotation_post(request):
    data = request.POST.copy()
    paragraphs = request.POST.getlist('covering_letter_paragraphs')
    if paragraphs:
        data['covering_letter_body'] = paragraphs_to_body(paragraphs)
    return data


def _covering_letter_paragraphs_for_form(form, request=None):
    body = ''
    if request and request.method == 'POST':
        paragraphs = request.POST.getlist('covering_letter_paragraphs')
        if paragraphs:
            return paragraphs
        body = request.POST.get('covering_letter_body', '')
    elif form.is_bound:
        body = form.data.get('covering_letter_body', '')
    elif form.instance.pk:
        body = form.instance.covering_letter_body
    else:
        body = form.initial.get('covering_letter_body', '')
    return body_to_paragraphs(body) or ['']


def _quotation_form_extras(form, request=None):
    return {
        'covering_letter_paragraphs': _covering_letter_paragraphs_for_form(form, request),
        'can_manage_templates': can_manage_quotation_settings(request.user) if request else False,
        'can_manage_rates': can_manage_rate_cards(request.user) if request else False,
        'can_edit_signatory': can_edit_document_signatory(request.user) if request else False,
        'signatory_instance': form.instance,
    }


def _fill_line_from_rate_card(cleaned_data, is_material):
    item = cleaned_data.get('material_item' if is_material else 'service_item')
    if item:
        if not cleaned_data.get('description'):
            cleaned_data['description'] = item.description or item.service_name if not is_material else item.item_name
        if not cleaned_data.get('unit'):
            cleaned_data['unit'] = item.unit
        if not cleaned_data.get('unit_rate'):
            cleaned_data['unit_rate'] = item.rate
        if not cleaned_data.get('gst_percent'):
            cleaned_data['gst_percent'] = item.gst_percent
    return cleaned_data


@module_required(MODULE_QUOTATIONS)
def quotation_list(request):

    form = QuotationSearchForm(request.GET or None)
    qs = Quotation.objects.select_related('client', 'created_by', 'converted_order').order_by('-quotation_date')

    if form.is_valid():
        q = form.cleaned_data.get('q')
        if q:
            qs = qs.filter(
                Q(quotation_number__icontains=q)
                | Q(client__name__icontains=q)
                | Q(site_location__icontains=q)
                | Q(subject__icontains=q)
            )
        client = form.cleaned_data.get('client')
        if client:
            qs = qs.filter(client=client)
        status = form.cleaned_data.get('status')
        if status:
            qs = qs.filter(status=status)
        date_from = form.cleaned_data.get('date_from')
        if date_from:
            qs = qs.filter(quotation_date__gte=date_from)
        date_to = form.cleaned_data.get('date_to')
        if date_to:
            qs = qs.filter(quotation_date__lte=date_to)

    return render(request, 'quotations/quotation_list.html', {
        'quotations': qs[:200],
        'search_form': form,
        'can_edit': can_edit_quotations(request.user),
        'can_approve': can_approve_quotations(request.user),
    })


def _save_quotation_form(request, quotation, form, mat_formset, svc_formset):
    with transaction.atomic():
        q = form.save(commit=False)
        if not q.pk:
            q.created_by = request.user
        q.save()
        mat_formset.instance = q
        svc_formset.instance = q
        mat_formset.save()
        svc_formset.save()
        q.recalculate_totals()
        q.save(update_fields=['subtotal', 'gst_total', 'grand_total', 'updated_at'])
    return q


@module_required(MODULE_QUOTATIONS)
def quotation_create(request):
    if request.method == 'POST':
        form = QuotationForm(_prepare_quotation_post(request), request.FILES, user=request.user)
        mat_formset = MaterialLineFormSet(request.POST, prefix='materials')
        svc_formset = ServiceLineFormSet(request.POST, prefix='services')
        if form.is_valid() and mat_formset.is_valid() and svc_formset.is_valid():
            with transaction.atomic():
                q = form.save(commit=False)
                q.created_by = request.user
                q.save()
                mat_formset.instance = q
                svc_formset.instance = q
                mat_formset.save()
                svc_formset.save()
                q.recalculate_totals()
                q.save(update_fields=['subtotal', 'gst_total', 'grand_total'])
            from productivity.activity_logger import log_activity
            from productivity.constants import ACT_QUOTATION_CREATED
            log_activity(
                request.user, ACT_QUOTATION_CREATED,
                related_document=q.quotation_number,
                related_model='Quotation',
                related_object_id=q.pk,
            )
            from case_intelligence.integrations import quotation_created
            quotation_created(request.user, q)
            messages.success(request, f'Quotation {q.quotation_number} created.')
            return redirect('quotation_detail', pk=q.pk)
    else:
        client_id = request.GET.get('client')
        initial = {}
        if client_id:
            from clients.models import Client
            try:
                c = Client.objects.get(pk=client_id)
                initial = {'client': c, 'contact_person': c.contact_person, 'site_location': c.address}
            except Client.DoesNotExist:
                pass
        form = QuotationForm(initial=initial, user=request.user)
        mat_formset = MaterialLineFormSet(prefix='materials')
        svc_formset = ServiceLineFormSet(prefix='services')

    ctx = {
        'form': form,
        'mat_formset': mat_formset,
        'svc_formset': svc_formset,
        'title': 'Create Quotation',
        'is_editable': True,
    }
    ctx.update(_quotation_form_extras(form, request))
    return render(request, 'quotations/quotation_form.html', ctx)


@module_required(MODULE_QUOTATIONS)
def quotation_detail(request, pk):

    quotation = get_object_or_404(
        Quotation.objects.select_related('client', 'created_by', 'approved_by', 'converted_order'),
        pk=pk,
    )
    doc = quotation_document_sections(quotation)
    cl = covering_letter_context(quotation)
    from case_intelligence.constants import MOD_QUOTATION
    from case_intelligence.services import panel_context
    case_ctx = panel_context(
        quotation,
        module=MOD_QUOTATION,
        document_number=quotation.quotation_number,
        status=quotation.get_status_display(),
        stage=quotation.get_status_display(),
        pending_action='Client approval' if quotation.status in ('SENT', 'UNDER_REVIEW') else '—',
        next_action='Convert to order' if quotation.status in ('APPROVED', 'ACCEPTED') else '—',
    )
    return render(request, 'quotations/quotation_detail.html', {
        'quotation': quotation,
        'can_edit': can_edit_quotations(request.user) and quotation.is_editable,
        'can_approve': can_approve_quotations(request.user),
        'material_lines': quotation.material_lines.select_related('material_item'),
        'service_lines': quotation.service_lines.select_related('service_item'),
        'doc': doc,
        'cl': cl,
        **case_ctx,
    })


@module_required(MODULE_QUOTATIONS)
def quotation_edit(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    if not quotation.is_editable:
        messages.error(request, 'This quotation cannot be edited in its current status.')
        return redirect('quotation_detail', pk=pk)

    if request.method == 'POST':
        form = QuotationForm(_prepare_quotation_post(request), request.FILES, instance=quotation, user=request.user)
        mat_formset = MaterialLineFormSet(request.POST, instance=quotation, prefix='materials')
        svc_formset = ServiceLineFormSet(request.POST, instance=quotation, prefix='services')
        if form.is_valid() and mat_formset.is_valid() and svc_formset.is_valid():
            _save_quotation_form(request, quotation, form, mat_formset, svc_formset)
            messages.success(request, 'Quotation updated.')
            return redirect('quotation_detail', pk=pk)
    else:
        form = QuotationForm(instance=quotation, user=request.user)
        mat_formset = MaterialLineFormSet(instance=quotation, prefix='materials')
        svc_formset = ServiceLineFormSet(instance=quotation, prefix='services')

    ctx = {
        'form': form,
        'mat_formset': mat_formset,
        'svc_formset': svc_formset,
        'quotation': quotation,
        'title': f'Edit {quotation.quotation_number}',
        'is_editable': True,
    }
    ctx.update(_quotation_form_extras(form, request))
    return render(request, 'quotations/quotation_form.html', ctx)


@module_required(MODULE_QUOTATIONS)
def quotation_pdf(request, pk):
    quotation = get_object_or_404(Quotation.objects.select_related('client'), pk=pk)
    pdf = build_proposal_pdf(quotation)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{quotation.quotation_number}.pdf"'
    return response


@module_required(MODULE_QUOTATIONS)
def quotation_print(request, pk):
    quotation = get_object_or_404(
        Quotation.objects.select_related('client', 'created_by', 'approved_by'),
        pk=pk,
    )
    doc = quotation_document_sections(quotation)
    cl = covering_letter_context(quotation)
    return render(request, 'quotations/quotation_print.html', {
        'quotation': quotation,
        'doc': doc,
        'cl': cl,
        'material_lines': quotation.material_lines.all(),
        'service_lines': quotation.service_lines.all(),
    })


@module_required(MODULE_QUOTATIONS)
def quotation_settings(request):
    if not can_view_quotation_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)

    settings_obj = QuotationSettings.get_solo()
    can_edit = can_manage_quotation_settings(request.user)

    if request.method == 'POST':
        if not can_edit:
            return access_denied_response(request, reason=REASON_ROLE)
        form = QuotationSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Quotation master settings updated.')
            return redirect('quotation_settings')
    else:
        form = QuotationSettingsForm(instance=settings_obj)
        if not can_edit:
            for field in form.fields.values():
                field.disabled = True

    return render(request, 'quotations/quotation_settings.html', {
        'form': form,
        'settings_obj': settings_obj,
        'can_edit': can_edit,
    })


@module_required(MODULE_QUOTATIONS)
def covering_letter_settings(request):
    if not can_view_quotation_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)

    settings_obj = CoveringLetterSettings.get_solo()
    can_edit = can_manage_quotation_settings(request.user)

    if request.method == 'POST':
        if not can_edit:
            return access_denied_response(request, reason=REASON_ROLE)
        form = CoveringLetterSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Covering letter settings updated.')
            return redirect('covering_letter_settings')
    else:
        form = CoveringLetterSettingsForm(instance=settings_obj)
        if not can_edit:
            for field in form.fields.values():
                field.disabled = True

    return render(request, 'quotations/covering_letter_settings.html', {
        'form': form,
        'settings_obj': settings_obj,
        'can_edit': can_edit,
    })


@module_required(MODULE_QUOTATIONS)
def covering_letter_preview(request, pk):
    quotation = get_object_or_404(Quotation.objects.select_related('client'), pk=pk)
    cl = covering_letter_context(quotation)
    return render(request, 'quotations/covering_letter_preview.html', {
        'quotation': quotation,
        'cl': cl,
    })


@module_required(MODULE_QUOTATIONS)
def covering_letter_print(request, pk):
    quotation = get_object_or_404(Quotation.objects.select_related('client'), pk=pk)
    cl = covering_letter_context(quotation)
    return render(request, 'quotations/covering_letter_print.html', {
        'quotation': quotation,
        'cl': cl,
    })


@module_required(MODULE_QUOTATIONS)
def proposal_template_list(request):
    ProposalTemplate.ensure_seed_templates()
    templates = ProposalTemplate.objects.select_related('created_by')
    return render(request, 'quotations/proposal_template_list.html', {
        'templates': templates,
        'can_manage': can_manage_quotation_settings(request.user),
    })


@module_required(MODULE_QUOTATIONS)
def proposal_template_create(request):
    if not can_manage_quotation_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    if request.method == 'POST':
        form = ProposalTemplateForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, f'Template "{obj.name}" created.')
            return redirect('proposal_template_list')
    else:
        form = ProposalTemplateForm()
    return render(request, 'quotations/proposal_template_form.html', {
        'form': form, 'title': 'Create Proposal Template',
    })


@module_required(MODULE_QUOTATIONS)
def proposal_template_edit(request, pk):
    if not can_manage_quotation_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    obj = get_object_or_404(ProposalTemplate, pk=pk)
    if request.method == 'POST':
        form = ProposalTemplateForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Template updated.')
            return redirect('proposal_template_list')
    else:
        form = ProposalTemplateForm(instance=obj)
    return render(request, 'quotations/proposal_template_form.html', {
        'form': form, 'title': f'Edit {obj.name}', 'template': obj,
    })


@module_required(MODULE_QUOTATIONS)
def proposal_template_delete(request, pk):
    if not can_manage_quotation_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    obj = get_object_or_404(ProposalTemplate, pk=pk)
    if request.method == 'POST':
        name = obj.name
        was_default = obj.is_default
        obj.delete()
        if was_default:
            first = ProposalTemplate.objects.order_by('pk').first()
            if first:
                first.is_default = True
                first.save()
        messages.success(request, f'Template "{name}" deleted.')
        return redirect('proposal_template_list')
    return render(request, 'quotations/proposal_template_delete.html', {'template': obj})


@module_required(MODULE_QUOTATIONS)
def proposal_template_duplicate(request, pk):
    if not can_manage_quotation_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    obj = get_object_or_404(ProposalTemplate, pk=pk)
    copy = ProposalTemplate.objects.create(
        name=f'{obj.name} (Copy)',
        subject=obj.subject,
        body=obj.body,
        is_default=False,
        created_by=request.user,
    )
    messages.success(request, f'Template duplicated as "{copy.name}".')
    return redirect('proposal_template_edit', pk=copy.pk)


@module_required(MODULE_QUOTATIONS)
def proposal_template_set_default(request, pk):
    if not can_manage_quotation_settings(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    obj = get_object_or_404(ProposalTemplate, pk=pk)
    obj.is_default = True
    obj.save()
    messages.success(request, f'"{obj.name}" set as default template.')
    return redirect('proposal_template_list')


@login_required
def proposal_template_api(request):
    if not can_view_quotations(request.user):
        return HttpResponseForbidden()
    from django.http import JsonResponse
    pk = request.GET.get('id')
    if not pk:
        return JsonResponse({})
    obj = get_object_or_404(ProposalTemplate, pk=pk)
    return JsonResponse({
        'subject': obj.subject,
        'body': obj.body,
        'paragraphs': body_to_paragraphs(obj.body),
    })


def _workflow_action(request, pk, new_status, label):
    if not can_approve_quotations(request.user) and new_status in ('APPROVED', 'UNDER_REVIEW'):
        return HttpResponseForbidden('Not allowed')
    if new_status == 'UNDER_REVIEW' and not can_edit_quotations(request.user):
        return HttpResponseForbidden('Not allowed')

    quotation = get_object_or_404(Quotation, pk=pk)
    if request.method == 'POST':
        if not quotation.can_transition_to(new_status):
            messages.error(request, f'Cannot change status from {quotation.get_status_display()} to {label}.')
            return redirect('quotation_detail', pk=pk)
        old_status = quotation.status
        quotation.status = new_status
        if new_status == 'APPROVED':
            quotation.approved_by = request.user
        quotation.save()
        from case_intelligence.integrations import quotation_approved, quotation_submitted
        from case_intelligence.logger import log_case_event
        from case_intelligence.constants import MOD_QUOTATION
        if new_status == 'SENT':
            quotation_submitted(request.user, quotation)
        elif new_status == 'APPROVED':
            quotation_approved(request.user, quotation)
        else:
            log_case_event(
                request.user,
                module=MOD_QUOTATION,
                document_type='Quotation',
                document_number=quotation.quotation_number,
                description=f'Quotation {label}',
                new_status=new_status,
                client=quotation.client,
                content_object=quotation,
            )
        messages.success(request, f'Quotation marked as {label}.')
        return redirect('quotation_detail', pk=pk)
    return render(request, 'quotations/quotation_action.html', {
        'quotation': quotation,
        'action_label': label,
        'new_status': new_status,
    })


@role_required('DIRECTOR', 'OPERATIONS')
def quotation_submit_review(request, pk):
    return _workflow_action(request, pk, 'UNDER_REVIEW', 'Under Review')


@role_required('DIRECTOR', 'OPERATIONS')
def quotation_approve(request, pk):
    return _workflow_action(request, pk, 'APPROVED', 'Approved')


@role_required('DIRECTOR', 'OPERATIONS')
def quotation_mark_sent(request, pk):
    return _workflow_action(request, pk, 'SENT', 'Sent')


@role_required('DIRECTOR', 'OPERATIONS')
def quotation_accept(request, pk):
    return _workflow_action(request, pk, 'ACCEPTED', 'Accepted')


@role_required('DIRECTOR', 'OPERATIONS')
def quotation_reject(request, pk):
    return _workflow_action(request, pk, 'REJECTED', 'Rejected')


@module_required(MODULE_QUOTATIONS)
def quotation_create_from_enquiry(request, enquiry_pk):
    from enquiries.models import Enquiry
    enquiry = get_object_or_404(Enquiry, pk=enquiry_pk)
    if request.method == 'POST':
        estimate_id = request.POST.get('estimate_boq')
        estimate_boq = None
        if estimate_id:
            from estimate_boq.models import EstimateBOQ
            estimate_boq = get_object_or_404(EstimateBOQ, pk=estimate_id, enquiry=enquiry)
        q = services.create_quotation_from_enquiry(enquiry, request.user, estimate_boq=estimate_boq)
        from case_intelligence.integrations import quotation_created
        quotation_created(request.user, q)
        messages.success(request, f'Quotation {q.quotation_number} created from enquiry.')
        return redirect('quotation_edit', pk=q.pk)
    return render(request, 'quotations/quotation_from_enquiry.html', {
        'enquiry': enquiry,
        'estimate_boqs': enquiry.estimate_boqs.all(),
    })


@role_required('DIRECTOR', 'OPERATIONS', 'PROJECT_MANAGER')
def quotation_convert_order(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    if quotation.converted_order_id:
        messages.info(request, f'Already linked to order {quotation.converted_order.order_no}.')
        return redirect('order_detail', pk=quotation.converted_order_id)

    if request.method == 'POST':
        try:
            order = services.convert_quotation_to_order(quotation, request.user)
            from case_intelligence.integrations import order_created, order_converted_from_enquiry
            if quotation.enquiry_id:
                order_converted_from_enquiry(request.user, order, quotation.enquiry)
            else:
                order_created(request.user, order, remarks=quotation.quotation_number)
            messages.success(
                request,
                f'Order {order.order_no} created from {quotation.quotation_number}.',
            )
            return redirect('order_detail', pk=order.pk)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('quotation_detail', pk=pk)

    return render(request, 'quotations/quotation_convert.html', {'quotation': quotation})


# —— Rate cards ——

@module_required(MODULE_QUOTATION_RATES)
def service_rate_list(request):
    rates = ServiceRateCard.objects.all()
    active = request.GET.get('active')
    if active == '1':
        rates = rates.filter(is_active=True)
    elif active == '0':
        rates = rates.filter(is_active=False)
    return render(request, 'quotations/service_rate_list.html', {
        'rates': rates,
        'can_manage': can_manage_rate_cards(request.user),
    })


@module_required(MODULE_QUOTATION_RATES)
def service_rate_create(request):
    if request.method == 'POST':
        form = ServiceRateCardForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            services.save_rate_card_with_audit('SERVICE', obj, request.user, is_new=True)
            messages.success(request, 'Service rate card added.')
            return redirect('service_rate_list')
    else:
        form = ServiceRateCardForm()
    return render(request, 'quotations/service_rate_form.html', {
        'form': form, 'title': 'Add Service Rate',
    })


@module_required(MODULE_QUOTATION_RATES)
def service_rate_edit(request, pk):
    obj = get_object_or_404(ServiceRateCard, pk=pk)
    if request.method == 'POST':
        form = ServiceRateCardForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            services.save_rate_card_with_audit('SERVICE', obj, request.user)
            messages.success(request, 'Service rate updated.')
            return redirect('service_rate_list')
    else:
        form = ServiceRateCardForm(instance=obj)
    return render(request, 'quotations/service_rate_form.html', {
        'form': form, 'title': f'Edit {obj.service_code}', 'rate': obj,
    })


@module_required(MODULE_QUOTATION_RATES)
def service_rate_delete(request, pk):
    obj = get_object_or_404(ServiceRateCard, pk=pk)
    if request.method == 'POST':
        services.delete_rate_card_with_audit('SERVICE', obj, request.user)
        messages.success(request, 'Service rate deleted.')
        return redirect('service_rate_list')
    return render(request, 'quotations/rate_delete_confirm.html', {
        'item': obj, 'rate_type': 'Service',
    })


@module_required(MODULE_QUOTATION_RATES)
def material_rate_list(request):
    rates = MaterialRateCard.objects.all()
    active = request.GET.get('active')
    if active == '1':
        rates = rates.filter(is_active=True)
    elif active == '0':
        rates = rates.filter(is_active=False)
    return render(request, 'quotations/material_rate_list.html', {
        'rates': rates,
        'can_manage': can_manage_rate_cards(request.user),
    })


@module_required(MODULE_QUOTATION_RATES)
def material_rate_create(request):
    if request.method == 'POST':
        form = MaterialRateCardForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            services.save_rate_card_with_audit('MATERIAL', obj, request.user, is_new=True)
            messages.success(request, 'Material rate card added.')
            return redirect('material_rate_list')
    else:
        form = MaterialRateCardForm()
    return render(request, 'quotations/material_rate_form.html', {
        'form': form, 'title': 'Add Material Rate',
    })


@module_required(MODULE_QUOTATION_RATES)
def material_rate_edit(request, pk):
    obj = get_object_or_404(MaterialRateCard, pk=pk)
    if request.method == 'POST':
        form = MaterialRateCardForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            services.save_rate_card_with_audit('MATERIAL', obj, request.user)
            messages.success(request, 'Material rate updated.')
            return redirect('material_rate_list')
    else:
        form = MaterialRateCardForm(instance=obj)
    return render(request, 'quotations/material_rate_form.html', {
        'form': form, 'title': f'Edit {obj.item_code}', 'rate': obj,
    })


@module_required(MODULE_QUOTATION_RATES)
def material_rate_delete(request, pk):
    obj = get_object_or_404(MaterialRateCard, pk=pk)
    if request.method == 'POST':
        services.delete_rate_card_with_audit('MATERIAL', obj, request.user)
        messages.success(request, 'Material rate deleted.')
        return redirect('material_rate_list')
    return render(request, 'quotations/rate_delete_confirm.html', {
        'item': obj, 'rate_type': 'Material',
    })


@module_required(MODULE_QUOTATION_RATES)
def rate_audit_list(request):
    logs = RateCardAuditLog.objects.select_related('revised_by')[:300]
    rate_type = request.GET.get('type')
    if rate_type in ('SERVICE', 'MATERIAL'):
        logs = logs.filter(rate_type=rate_type)
    return render(request, 'quotations/rate_audit_list.html', {'logs': logs})


@login_required
def rate_card_api(request):
    """JSON helper for auto-fill in quotation form."""
    if not can_view_quotations(request.user):
        return HttpResponseForbidden()
    from django.http import JsonResponse
    kind = request.GET.get('kind')
    pk = request.GET.get('id')
    if kind == 'service' and pk:
        item = get_object_or_404(ServiceRateCard, pk=pk, is_active=True)
        return JsonResponse({
            'description': item.description or item.service_name,
            'unit': item.unit,
            'unit_rate': str(item.rate),
            'gst_percent': str(item.gst_percent),
        })
    if kind == 'material' and pk:
        item = get_object_or_404(MaterialRateCard, pk=pk, is_active=True)
        return JsonResponse({
            'description': item.description or item.item_name,
            'unit': item.unit,
            'unit_rate': str(item.rate),
            'gst_percent': str(item.gst_percent),
        })
    return JsonResponse({})
