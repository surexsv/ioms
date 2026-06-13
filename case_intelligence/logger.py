"""Central case activity logger — always on (independent of productivity toggle)."""

from django.contrib.contenttypes.models import ContentType

from accounts.roles import user_role
from case_intelligence.models import CaseActivityLog


def log_case_event(
    user,
    *,
    module,
    document_type,
    document_number,
    description,
    previous_status='',
    new_status='',
    remarks='',
    client=None,
    content_object=None,
):
    """Record a case lifecycle event. Safe to call from any module view/service."""
    if not document_number:
        return None
    ct = None
    oid = None
    if content_object is not None:
        ct = ContentType.objects.get_for_model(content_object)
        oid = content_object.pk
    return CaseActivityLog.objects.create(
        module=module,
        document_type=document_type,
        document_number=str(document_number)[:60],
        description=description[:200],
        previous_status=(previous_status or '')[:50],
        new_status=(new_status or '')[:50],
        user=user if user and getattr(user, 'is_authenticated', False) else None,
        user_role=user_role(user) if user and getattr(user, 'is_authenticated', False) else '',
        remarks=remarks,
        client=client,
        content_type=ct,
        object_id=oid,
    )
