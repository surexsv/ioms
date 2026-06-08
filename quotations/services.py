from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from orders.models import Order
from .models import RateCardAuditLog, Quotation


def log_rate_card_change(rate_type, instance, action, user, field_name='', old_value='', new_value=''):
    code = getattr(instance, 'service_code', None) or getattr(instance, 'item_code', '')
    name = getattr(instance, 'service_name', None) or getattr(instance, 'item_name', '')
    RateCardAuditLog.objects.create(
        rate_type=rate_type,
        record_code=code,
        record_name=name,
        action=action,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        revised_by=user,
    )


def save_rate_card_with_audit(rate_type, instance, user, is_new=False):
    tracked = ('rate', 'gst_percent', 'is_active', 'unit', 'description')
    if is_new:
        instance.rate_revision_date = timezone.now().date()
        instance.last_updated_by = user
        instance.save()
        log_rate_card_change(rate_type, instance, 'CREATE', user)
        return

    if instance.pk:
        from .models import ServiceRateCard, MaterialRateCard
        Model = ServiceRateCard if rate_type == 'SERVICE' else MaterialRateCard
        old = Model.objects.get(pk=instance.pk)
        changed = False
        for field in tracked:
            old_val = getattr(old, field)
            new_val = getattr(instance, field)
            if old_val != new_val:
                log_rate_card_change(
                    rate_type, instance, 'UPDATE', user,
                    field_name=field, old_value=old_val, new_value=new_val,
                )
                changed = True
        if changed:
            instance.rate_revision_date = timezone.now().date()
    instance.last_updated_by = user
    instance.save()


def delete_rate_card_with_audit(rate_type, instance, user):
    log_rate_card_change(rate_type, instance, 'DELETE', user)
    instance.delete()


@transaction.atomic
def convert_quotation_to_order(quotation, user):
    if quotation.converted_order_id:
        return quotation.converted_order

    if quotation.status not in ('ACCEPTED', 'APPROVED', 'SENT'):
        raise ValueError('Quotation must be accepted, approved, or sent before conversion.')

    materials = '\n'.join(
        f"- {line.description} x {line.quantity} {line.unit} @ {line.unit_rate}"
        for line in quotation.material_lines.all()
    )
    services = '\n'.join(
        f"- {line.description} x {line.quantity} {line.unit} @ {line.unit_rate}"
        for line in quotation.service_lines.all()
    )
    description = (
        f"Converted from {quotation.quotation_number}\n\n"
        f"Subject: {quotation.subject}\n\n"
        f"Scope of Work:\n{quotation.scope_of_work}\n\n"
    )
    if materials:
        description += f"Materials:\n{materials}\n\n"
    if services:
        description += f"Services:\n{services}\n"

    target = quotation.valid_until
    if target < timezone.now().date():
        target = timezone.now().date() + timedelta(days=30)

    order = Order.objects.create(
        client=quotation.client,
        site_address=quotation.site_location,
        order_type='INSTALLATION',
        description=description,
        priority='Normal',
        expected_completion_date=target,
        status='NEW',
    )
    quotation.converted_order = order
    quotation.status = 'CONVERTED'
    quotation.save(update_fields=['converted_order', 'status', 'updated_at'])
    return order
