"""Attendance utilities — device info, IP, geocoding, maps links."""

import json
import urllib.parse
import urllib.request

from django.utils import timezone


def get_client_ip(request):
    if not request:
        return ''
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


def get_device_info(request):
    if not request:
        return ''
    ua = request.META.get('HTTP_USER_AGENT', '')[:500]
    return ua


def maps_link(latitude, longitude):
    if latitude is None or longitude is None:
        return ''
    return 'https://www.google.com/maps?q=' + urllib.parse.quote(f'{latitude},{longitude}')


def reverse_geocode(latitude, longitude, timeout=4):
    if latitude is None or longitude is None:
        return ''
    try:
        url = (
            'https://nominatim.openstreetmap.org/reverse?'
            + urllib.parse.urlencode({'lat': str(latitude), 'lon': str(longitude), 'format': 'json'})
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'IOMS-Attendance/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return (data.get('display_name') or '')[:500]
    except Exception:
        return f'{latitude}, {longitude}'


def attendance_now():
    return timezone.localtime()
