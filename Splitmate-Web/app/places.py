"""Turns a "lat, lng" from the browser into a place name people recognise (for grocery price lookups)."""
import json
import logging
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

REVERSE_URL = 'https://nominatim.openstreetmap.org/reverse'
USER_AGENT = 'Splitmate/1.0 (grocery price comparison)'
_cache = {}


def _coordinate(value, limit):
    number = float(value)
    if not -limit <= number <= limit:
        raise ValueError('out of range')
    return round(number, 3)


def place_name(lat, lng, fetch=None):
    """'Downtown, Toronto, M5V 2T6' style text, or None if the lookup fails.

    Rounded to about 100 m so we never send a precise position, and cached for a day.
    """
    lat, lng = _coordinate(lat, 90), _coordinate(lng, 180)
    key = (lat, lng)
    cached = _cache.get(key)
    if cached and cached[1] > time.time():
        return cached[0]
    try:
        if fetch:
            data = fetch(lat, lng)
        else:
            query = urlencode({'lat': lat, 'lon': lng, 'format': 'jsonv2', 'zoom': 16, 'addressdetails': 1})
            request = Request(f'{REVERSE_URL}?{query}', headers={'User-Agent': USER_AGENT, 'Accept-Language': 'en'})
            with urlopen(request, timeout=6) as response:
                data = json.loads(response.read().decode('utf-8'))
    except Exception as exc:  # Network down or rate limited: the caller keeps the coordinates.
        logger.warning('Reverse geocoding failed: %s', exc)
        return None
    address = (data or {}).get('address') or {}
    area = address.get('neighbourhood') or address.get('suburb') or address.get('quarter')
    city = address.get('city') or address.get('town') or address.get('village') or address.get('municipality')
    parts = [part for part in (area, city, address.get('postcode')) if part]
    name = ', '.join(dict.fromkeys(parts)) or None
    if name:
        _cache[key] = (name, time.time() + 86400)
    return name
