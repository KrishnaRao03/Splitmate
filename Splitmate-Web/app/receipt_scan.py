"""Reads the line items off a receipt photo with Google's Gemini vision model."""
import json
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx
from google import genai
from google.genai import errors, types

RECEIPT_MODEL = os.environ.get('RECEIPT_SCAN_MODEL') or 'gemini-3.6-flash'
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
# Keep uploads small; inline images must fit in one request.
MAX_IMAGE_BYTES = 5 * 1024 * 1024

RECEIPT_SCHEMA = {
    'type': 'object',
    'properties': {
        'is_receipt': {'type': 'boolean'},
        'merchant': {'type': 'string'},
        'currency': {'type': 'string'},
        'items': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'quantity': {'type': 'number'},
                    'price': {'type': 'number'},
                },
                'required': ['name', 'quantity', 'price'],
                'additionalProperties': False,
            },
        },
        'tax': {'type': 'number'},
        'total': {'type': 'number'},
    },
    'required': ['is_receipt', 'merchant', 'currency', 'items', 'tax', 'total'],
    'additionalProperties': False,
}

PROMPT = """Read this receipt and list what was bought.

- One entry per purchased line. `price` is the line's total as printed (already multiplied by quantity), `quantity` is the count (1 if not shown).
- Use clean, readable item names: expand obvious abbreviations, but don't invent items you can't read.
- Discounts or coupons that apply to a line: subtract them from that line's price. Store-wide discounts: add a line with a negative price.
- Don't list subtotal, tax, tip, payment, change or loyalty lines as items. Put the total tax in `tax` and the final amount paid in `total` (0 if not shown).
- `merchant` is the store name ('' if unreadable); `currency` is the ISO code if you can tell, else ''.
- If the image is not a receipt, set `is_receipt` to false and return no items."""


class ReceiptScanError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def scanning_configured():
    return bool(os.environ.get('GEMINI_API_KEY'))


def _money(value):
    try:
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0


def scan_receipt_image(data, media_type, client=None):
    """Returns {merchant, currency, items: [{name, quantity, price}], tax, total}."""
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise ReceiptScanError('Upload a JPG, PNG, WEBP or GIF photo of the receipt.')
    if not data:
        raise ReceiptScanError('The receipt photo was empty.')
    if len(data) > MAX_IMAGE_BYTES:
        raise ReceiptScanError('That photo is over 5 MB. Try a smaller or lower-resolution photo.')
    if client is None:
        if not scanning_configured():
            raise ReceiptScanError(
                'Receipt scanning is not set up on the server yet. Add GEMINI_API_KEY to the server .env and restart it.',
                503,
            )
        client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

    try:
        response = client.models.generate_content(
            model=RECEIPT_MODEL,
            contents=[types.Part.from_bytes(data=data, mime_type=media_type), PROMPT],
            config=types.GenerateContentConfig(
                max_output_tokens=16000,
                response_mime_type='application/json',
                response_json_schema=RECEIPT_SCHEMA,
            ),
        )
    except errors.ClientError as exc:
        if exc.code == 429:
            raise ReceiptScanError('Receipt scanning is busy right now. Try again in a minute.', 429)
        if exc.code in (401, 403) or 'API key' in (exc.message or ''):
            raise ReceiptScanError('The server\'s Gemini API key was rejected. Check GEMINI_API_KEY in .env.', 503)
        raise ReceiptScanError(f'The receipt could not be read: {exc.message}', 400)
    except errors.APIError:
        raise ReceiptScanError('Receipt scanning is temporarily unavailable. Try again shortly.', 502)
    except httpx.TransportError:
        raise ReceiptScanError('The server could not reach the receipt scanner. Check its internet connection.', 502)

    candidate = (response.candidates or [None])[0]
    if getattr(candidate, 'finish_reason', None) == types.FinishReason.MAX_TOKENS:
        raise ReceiptScanError('That receipt is too long to scan in one go. Enter it by hand or crop it.', 422)
    # No text back means Gemini blocked the image (safety filters) or returned nothing usable.
    text = response.text
    if not text:
        raise ReceiptScanError('This image could not be scanned. Try another photo or enter the expense by hand.', 422)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        raise ReceiptScanError('The receipt could not be read. Try a clearer photo.', 422)

    if not parsed.get('is_receipt'):
        raise ReceiptScanError('That doesn\'t look like a receipt. Try a clearer photo of the whole receipt.', 422)

    items = []
    for row in parsed.get('items') or []:
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        quantity = row.get('quantity') or 1
        items.append({
            'name': name[:120],
            'quantity': quantity if isinstance(quantity, (int, float)) and quantity > 0 else 1,
            'price': _money(row.get('price')),
        })
    if not items:
        raise ReceiptScanError('No items could be read from that receipt. Try a clearer photo.', 422)

    return {
        'merchant': str(parsed.get('merchant') or '').strip()[:120],
        'currency': str(parsed.get('currency') or '').strip().upper()[:3],
        'items': items,
        'tax': _money(parsed.get('tax')),
        'total': _money(parsed.get('total')),
    }
