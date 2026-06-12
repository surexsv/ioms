from django.db import transaction
from django.utils import timezone

from orders.models import Order
from .models import Enquiry


@transaction.atomic
def convert_enquiry_to_order(enquiry, user):
    """Create order from won enquiry or approved quotation."""
    if enquiry.converted_order_id:
        return enquiry.converted_order

    if not enquiry.can_convert_to_order:
        raise ValueError(
            'Enquiry must be WON or have an approved/sent/accepted quotation before conversion.',
        )

    approved_quotation = enquiry.quotations.filter(
        status__in=('APPROVED', 'ACCEPTED', 'SENT'),
    ).order_by('-updated_at').first()

    if approved_quotation:
        from quotations.services import convert_quotation_to_order
        order = convert_quotation_to_order(approved_quotation, user)
        enquiry.converted_order = order
        enquiry.status = Enquiry.STATUS_CONVERTED
        enquiry.save(update_fields=['converted_order', 'status', 'updated_at'])
        return order

    description = enquiry.description
    estimate = getattr(enquiry, 'estimate_boqs', None)
    if estimate and estimate.exists():
        eboq = estimate.order_by('-created_at').first()
        lines = '\n'.join(
            f"- {line.item}: {line.description} x {line.quantity} {line.unit} @ {line.rate}"
            for line in eboq.lines.all()
        )
        if lines:
            description += f"\n\nApproved Estimate BOQ ({eboq.estimate_boq_number}):\n{lines}"

    order = Order.objects.create(
        client=enquiry.client,
        project_site_name=enquiry.client.name,
        site_address=enquiry.location,
        order_type=enquiry.enquiry_type if enquiry.enquiry_type != 'AMC' else 'MAINTENANCE',
        description=description,
        priority='Normal',
        status='NEW',
    )
    enquiry.converted_order = order
    enquiry.status = Enquiry.STATUS_CONVERTED
    enquiry.save(update_fields=['converted_order', 'status', 'updated_at'])
    return order
