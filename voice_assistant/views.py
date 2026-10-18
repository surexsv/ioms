import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.access_control import REASON_UNAUTHORIZED
from accounts.decorators import access_denied_response
from accounts.permissions import MODULE_ORDERS, MODULE_TASK_MANAGER, MODULE_WCR, can_access
from case_intelligence.constants import MOD_ORDER
from case_intelligence.logger import log_case_event
from orders.models import Order
from orders.views import _can_access_order

from .models import OrderVoiceNote
from .translate import VoiceTranslateError, malayalam_to_english


def _wants_json(request):
    if request.content_type == 'application/json':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


def _payload(request):
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            data = {}
        return data if isinstance(data, dict) else {}
    return request.POST


def _can_translate(user):
    if user.is_superuser:
        return True
    return (
        can_access(user, MODULE_ORDERS)
        or can_access(user, MODULE_WCR)
        or can_access(user, MODULE_TASK_MANAGER)
    )


@login_required
@require_POST
def translate_voice(request):
    if not _can_translate(request.user):
        return JsonResponse({'error': 'Not allowed.'}, status=403)
    text = (_payload(request).get('text') or '').strip()
    try:
        english, engine = malayalam_to_english(text)
    except VoiceTranslateError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'english': english, 'engine': engine})


@login_required
@require_POST
def save_voice_note(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not _can_access_order(request.user, order):
        if _wants_json(request):
            return JsonResponse({'error': 'Not allowed.'}, status=403)
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    data = _payload(request)
    kind = (data.get('kind') or '').strip()
    malayalam = (data.get('malayalam_text') or '').strip()
    english = (data.get('english_text') or '').strip()
    allowed = {code for code, _label in OrderVoiceNote.KIND_CHOICES}
    error = ''
    if kind not in allowed:
        error = 'Choose Order Update, Work Completion, or Closing Remarks.'
    elif not malayalam or not english:
        error = 'Review the Malayalam and the English, then confirm.'
    elif len(malayalam) > 4000 or len(english) > 4000:
        error = 'Keep each note under 4000 characters.'

    if error:
        if _wants_json(request):
            return JsonResponse({'error': error}, status=400)
        from django.contrib import messages
        messages.error(request, error)
        return redirect('order_detail', pk=order.pk)

    note = OrderVoiceNote.objects.create(
        order=order,
        kind=kind,
        malayalam_text=malayalam,
        english_text=english,
        created_by=request.user,
    )
    log_case_event(
        request.user,
        module=MOD_ORDER,
        document_type='Order',
        document_number=order.order_no or str(order.order_id),
        description=f'{note.get_kind_display()} recorded',
        remarks=english,
        client=order.client,
        content_object=order,
    )
    if _wants_json(request):
        return JsonResponse({'ok': True, 'id': note.pk})
    from django.contrib import messages
    messages.success(request, f'{note.get_kind_display()} saved on this order.')
    return redirect('order_detail', pk=order.pk)
