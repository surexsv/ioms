"""Turn a Malayalam field note into clear English.

An AI key in the environment writes professional English. Without a key, a
translation service still produces English so the technician can review it.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class VoiceTranslateError(Exception):
    pass


_MALAYALAM = set(range(0x0D00, 0x0D80))


def malayalam_to_english(text):
    text = (text or '').strip()
    if not text:
        raise VoiceTranslateError('Enter the Malayalam note first.')
    if len(text) > 4000:
        raise VoiceTranslateError('Keep the note under 4000 characters.')

    api_key = getattr(settings, 'IOMS_AI_API_KEY', '') or ''
    if api_key:
        try:
            return _ai_translate(text, api_key), 'ai'
        except VoiceTranslateError:
            pass

    english = _machine_translate(text)
    if not english or _mostly_malayalam(english):
        raise VoiceTranslateError(
            'English could not be prepared. Type the English version, then confirm.'
        )
    return _tidy_english(english), 'translation'


def _mostly_malayalam(text):
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    malayalam = sum(1 for ch in letters if ord(ch) in _MALAYALAM)
    return malayalam / len(letters) > 0.4


def _tidy_english(text):
    cleaned = ' '.join(text.replace('\n', ' ').split())
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned and cleaned[-1] not in '.!?':
        cleaned += '.'
    return cleaned


def _ai_translate(text, api_key):
    url = getattr(settings, 'IOMS_AI_API_URL', '') or 'https://api.openai.com/v1/chat/completions'
    model = getattr(settings, 'IOMS_AI_MODEL', '') or 'gpt-4o-mini'
    payload = {
        'model': model,
        'temperature': 0.2,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You translate Malayalam field-service notes into clear professional English. '
                    'Keep every fact, name, place, quantity, and time. Do not add information. '
                    'Return only the English paragraph.'
                ),
            },
            {'role': 'user', 'content': text},
        ],
    }
    raw = _post_json(
        url,
        payload,
        headers={'Authorization': f'Bearer {api_key}'},
    )
    try:
        english = raw['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise VoiceTranslateError('The AI service did not return English.') from exc
    if not english:
        raise VoiceTranslateError('The AI service did not return English.')
    return english


def _machine_translate(text):
    chunks = _chunks(text, 400)
    parts = []
    for chunk in chunks:
        translated = _mymemory(chunk) or _google(chunk)
        if not translated:
            raise VoiceTranslateError(
                'English could not be prepared. Type the English version, then confirm.'
            )
        parts.append(translated)
    return ' '.join(parts)


def _chunks(text, limit):
    if len(text) <= limit:
        return [text]
    pieces = []
    current = ''
    for word in text.split(' '):
        candidate = word if not current else f'{current} {word}'
        if len(candidate) > limit and current:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _mymemory(text):
    query = urllib.parse.urlencode({'q': text, 'langpair': 'ml|en'})
    url = 'https://api.mymemory.translated.net/get?' + query
    try:
        data = json.loads(_get(url))
    except (VoiceTranslateError, json.JSONDecodeError, UnicodeDecodeError):
        return ''
    translated = ((data or {}).get('responseData') or {}).get('translatedText') or ''
    upper = translated.upper()
    if 'QUERY LENGTH' in upper or 'INVALID' in upper or not translated.strip():
        return ''
    return translated.strip()


def _google(text):
    query = urllib.parse.urlencode({'client': 'gtx', 'sl': 'ml', 'tl': 'en', 'dt': 't', 'q': text})
    url = 'https://translate.googleapis.com/translate_a/single?' + query
    try:
        data = json.loads(_get(url))
    except (VoiceTranslateError, json.JSONDecodeError, UnicodeDecodeError):
        return ''
    if not data or not isinstance(data[0], list):
        return ''
    parts = []
    for row in data[0]:
        if row and row[0]:
            parts.append(row[0])
    return ''.join(parts).strip()


def _get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'IOMS-Voice/1.0'})
    return _read(request)


def _post_json(url, payload, headers=None):
    body = json.dumps(payload).encode()
    request_headers = {'Content-Type': 'application/json', 'User-Agent': 'IOMS-Voice/1.0'}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=body, headers=request_headers)
    raw = _read(request)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VoiceTranslateError('The AI service did not return English.') from exc


def _read(request):
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.read().decode()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VoiceTranslateError(
            'English could not be prepared. Type the English version, then confirm.'
        ) from exc
