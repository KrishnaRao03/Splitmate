"""Input rules shared by the web pages and the mobile API."""
import re
from decimal import Decimal
from urllib.parse import quote, urlencode, urlparse

from app.email_validation import normalize_email

MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 100
PAYPAL_USERNAME = re.compile(r'^[A-Za-z0-9]{1,20}$')
UPI_ID = re.compile(r'^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9.-]{1,48}$')


def display_name_error(value, label='Name'):
    """Names show up in other members' pages, so markup characters are refused outright."""
    name = (value or '').strip()
    if not name:
        return f'{label} is required.'
    if len(name) > MAX_NAME_LENGTH:
        return f'{label} must be {MAX_NAME_LENGTH} characters or fewer.'
    if '<' in name or '>' in name:
        return f'{label} cannot contain < or >.'
    return None


def password_error(password):
    if len(password or '') < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
    return None


def is_safe_link(url):
    """Receipt links must be plain web links (or our own relative paths), never javascript: or data:."""
    value = (url or '').strip()
    if not value:
        return True
    if value.startswith('/') and not value.startswith('//'):
        return True
    parsed = urlparse(value)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def csv_safe(value):
    """Stops spreadsheet apps from running a cell as a formula."""
    text = '' if value is None else str(value)
    if text[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + text
    return text


def clean_payment_handles(data):
    """Validates the optional Interac email, PayPal.Me username and UPI ID. Returns (values, error)."""
    values = {}
    if 'interac_email' in data:
        raw = (data.get('interac_email') or '').strip()
        email = normalize_email(raw) if raw else ''
        if raw and not email:
            return None, 'Enter a valid Interac e-Transfer email.'
        values['interac_email'] = email or None
    if 'paypal_username' in data:
        raw = (data.get('paypal_username') or '').strip().removeprefix('@')
        raw = re.sub(r'^(https?://)?(www\.)?paypal\.me/', '', raw, flags=re.IGNORECASE).strip('/')
        if raw and not PAYPAL_USERNAME.match(raw):
            return None, 'Enter your PayPal.Me username (letters and numbers only).'
        values['paypal_username'] = raw or None
    if 'upi_id' in data:
        raw = (data.get('upi_id') or '').strip()
        if raw and not UPI_ID.match(raw):
            return None, 'Enter a valid UPI ID, like name@bank.'
        values['upi_id'] = raw or None
    return values, None


def payment_methods_for(receiver, amount, currency_code, receiver_name=None):
    """Ways to pay `receiver` outside the app. Splitmate only builds links; it never touches the money."""
    amount_text = f'{Decimal(str(amount)):.2f}'
    name = receiver_name or receiver.name
    methods = []
    if receiver.interac_email:
        methods.append({
            'type': 'interac',
            'label': 'Interac e-Transfer',
            'handle': receiver.interac_email,
            'url': None,
        })
    if receiver.paypal_username:
        methods.append({
            'type': 'paypal',
            'label': 'PayPal',
            'handle': receiver.paypal_username,
            'url': f'https://paypal.me/{quote(receiver.paypal_username)}/{amount_text}{currency_code.upper()}',
        })
    if receiver.upi_id:
        params = {'pa': receiver.upi_id, 'pn': name}
        # UPI only settles in rupees; for other currencies the payer types the amount themselves.
        if currency_code.upper() == 'INR':
            params.update({'am': amount_text, 'cu': 'INR'})
        methods.append({
            'type': 'upi',
            'label': 'UPI',
            'handle': receiver.upi_id,
            'url': f'upi://pay?{urlencode(params, quote_via=quote)}',
        })
    return methods
