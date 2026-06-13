"""Schedule site check-in / check-out with GPS verification."""

from django.utils import timezone

from productivity.field_constants import FA_SITE_CHECK_IN, FA_SITE_CHECK_OUT
from productivity.gps_service import record_field_event, reverse_geocode


def get_or_create_attendance(schedule, employee):
    from productivity.models import ScheduleSiteAttendance
    att, _ = ScheduleSiteAttendance.objects.get_or_create(
        schedule=schedule,
        employee=employee,
    )
    return att


def site_check_in(schedule, employee, request=None, site_photo=None):
    from company_settings.field_ops import is_checkin_enabled, is_site_photos_enabled
    if not is_checkin_enabled():
        return None, False, 'Site check-in is disabled in field operations settings.'
    from productivity.models import ScheduleSiteAttendance

    att = get_or_create_attendance(schedule, employee)
    if att.check_in_at and not att.check_out_at:
        return att, False, 'Already checked in at this site.'

    now = timezone.now()
    lat = lng = None
    address = ''
    if request:
        from productivity.gps_service import extract_gps_from_request
        lat, lng = extract_gps_from_request(request)
        if lat and lng:
            address = reverse_geocode(lat, lng)

    att.check_in_at = now
    att.check_in_latitude = lat
    att.check_in_longitude = lng
    att.check_in_address = address
    if site_photo and not is_site_photos_enabled():
        site_photo = None
    if site_photo:
        att.site_photo = site_photo
    att.save()

    record_field_event(
        employee, FA_SITE_CHECK_IN,
        request=request,
        latitude=lat,
        longitude=lng,
        order=schedule.order if schedule.order_id else None,
        schedule=schedule,
        enquiry=schedule.enquiry if schedule.enquiry_id else None,
        remarks=f'Check-in: {schedule.schedule_number}',
        site_photo=site_photo,
    )
    return att, True, 'Site check-in recorded with GPS.'


def site_check_out(schedule, employee, request=None, work_photo=None):
    att = get_or_create_attendance(schedule, employee)
    if not att.check_in_at:
        return att, False, 'Please check in first.'
    if att.check_out_at:
        return att, False, 'Already checked out from this site.'

    now = timezone.now()
    lat = lng = None
    address = ''
    if request:
        from productivity.gps_service import extract_gps_from_request
        lat, lng = extract_gps_from_request(request)
        if lat and lng:
            address = reverse_geocode(lat, lng)

    att.check_out_at = now
    att.check_out_latitude = lat
    att.check_out_longitude = lng
    att.check_out_address = address
    if work_photo:
        att.work_photo = work_photo
    att.save()

    record_field_event(
        employee, FA_SITE_CHECK_OUT,
        request=request,
        latitude=lat,
        longitude=lng,
        order=schedule.order if schedule.order_id else None,
        schedule=schedule,
        enquiry=schedule.enquiry if schedule.enquiry_id else None,
        remarks=f'Check-out: {schedule.schedule_number}',
        work_photo=work_photo,
    )
    return att, True, 'Site check-out recorded with GPS.'
