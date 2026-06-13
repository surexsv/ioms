"""GPS capture, reverse geocoding, and field activity logging."""

import json
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from django.utils import timezone


def _parse_coord(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value)).quantize(Decimal('0.000001'))
    except (InvalidOperation, ValueError, TypeError):
        return None


def device_info_from_request(request):
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:250]


def extract_gps_from_request(request):
    lat = _parse_coord(request.POST.get('latitude') or request.GET.get('latitude'))
    lng = _parse_coord(request.POST.get('longitude') or request.GET.get('longitude'))
    return lat, lng


def reverse_geocode(latitude, longitude, timeout=5):
    if latitude is None or longitude is None:
        return ''
    params = urllib.parse.urlencode({
        'lat': str(latitude),
        'lon': str(longitude),
        'format': 'json',
        'addressdetails': '1',
        'zoom': '16',
    })
    url = f'https://nominatim.openstreetmap.org/reverse?{params}'
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'InfomatesOMS/1.3 (field-tracking; contact@infomates.in)'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return ''
    address = data.get('display_name', '')
    if not address and data.get('address'):
        addr = data['address']
        parts = [
            addr.get('road') or addr.get('pedestrian') or addr.get('neighbourhood'),
            addr.get('suburb') or addr.get('village') or addr.get('town'),
            addr.get('city') or addr.get('county'),
            addr.get('state'),
        ]
        address = ', '.join(p for p in parts if p)
    return address[:500]


def record_field_event(
    user,
    action_type,
    *,
    request=None,
    latitude=None,
    longitude=None,
    order=None,
    schedule=None,
    wcr=None,
    enquiry=None,
    remarks='',
    site_photo=None,
    work_photo=None,
):
    from productivity.models import FieldActivityLog, GPSLocationRecord

    if request and (latitude is None or longitude is None):
        req_lat, req_lng = extract_gps_from_request(request)
        latitude = latitude if latitude is not None else req_lat
        longitude = longitude if longitude is not None else req_lng

    device = device_info_from_request(request)
    now = timezone.now()
    address = reverse_geocode(latitude, longitude) if latitude and longitude else ''

    gps_record = None
    if latitude is not None and longitude is not None:
        gps_record = GPSLocationRecord.objects.create(
            latitude=latitude,
            longitude=longitude,
            address=address,
            captured_at=now,
            employee=user,
            device_info=device,
            action_type=action_type,
            order=order,
            schedule=schedule,
            wcr=wcr,
            enquiry=enquiry,
        )

    create_kwargs = {
        'employee': user,
        'role': getattr(user, 'role', '') or '',
        'order': order,
        'schedule': schedule,
        'wcr': wcr,
        'enquiry': enquiry,
        'action_type': action_type,
        'latitude': latitude,
        'longitude': longitude,
        'address': address,
        'activity_date': now.date(),
        'activity_time': now.time(),
        'device_info': device,
        'remarks': remarks,
        'gps_record': gps_record,
    }
    if site_photo:
        create_kwargs['site_photo'] = site_photo
    if work_photo:
        create_kwargs['work_photo'] = work_photo

    activity = FieldActivityLog.objects.create(**create_kwargs)
    return activity, gps_record


def record_order_status_gps(user, order, old_status, new_status, request=None):
    from productivity.field_constants import ORDER_STATUS_TO_ACTION
    action = ORDER_STATUS_TO_ACTION.get(new_status)
    if not action:
        return None
    schedule = getattr(order, 'work_schedule', None)
    return record_field_event(
        user, action,
        request=request,
        order=order,
        schedule=schedule,
        remarks=f'Order {order.order_no}: {old_status} → {new_status}',
    )


def record_schedule_status_gps(user, schedule, old_status, new_status, request=None):
    from productivity.field_constants import SCHEDULE_STATUS_TO_ACTION
    action = SCHEDULE_STATUS_TO_ACTION.get(new_status)
    if not action:
        return None
    return record_field_event(
        user, action,
        request=request,
        order=schedule.order,
        schedule=schedule,
        remarks=f'Schedule {schedule.schedule_number}: {old_status} → {new_status}',
    )


def record_survey_status_gps(user, enquiry, old_status, new_status, request=None):
    from productivity.field_constants import SURVEY_STATUS_TO_ACTION
    action = SURVEY_STATUS_TO_ACTION.get(new_status)
    if not action:
        return None
    return record_field_event(
        user, action,
        request=request,
        enquiry=enquiry,
        remarks=f'Enquiry {enquiry.enquiry_number}: {old_status} → {new_status}',
    )
