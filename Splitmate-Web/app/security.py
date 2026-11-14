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


PASSWORD_RULES = (
    f'Use at least {MIN_PASSWORD_LENGTH} characters with an uppercase letter, a lowercase letter, '
    'a number and a special character (like ! @ # $).'
)


def password_error(password):
    """Rules for new passwords only; sign-in never re-checks them, so older passwords keep working."""
    password = password or ''
    missing = []
    if len(password) < MIN_PASSWORD_LENGTH:
        missing.append(f'at least {MIN_PASSWORD_LENGTH} characters')
    if not re.search(r'[A-Z]', password):
        missing.append('an uppercase letter')
    if not re.search(r'[a-z]', password):
        missing.append('a lowercase letter')
    if not re.search(r'[0-9]', password):
        missing.append('a number')
    if not re.search(r'[^A-Za-z0-9]', password):
        missing.append('a special character (like ! @ # $)')
    if not missing:
        return None
    if len(missing) == 1:
        return f'Password needs {missing[0]}.'
    return 'Password needs ' + ', '.join(missing[:-1]) + f' and {missing[-1]}.'


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
    from app.regions import payment_fields_for

    amount_text = f'{Decimal(str(amount)):.2f}'
    name = receiver_name or receiver.name
    # Only the ways to pay that work in the receiver's country (Interac in Canada, UPI in India, PayPal anywhere).
    allowed = set(payment_fields_for(getattr(receiver, 'country', None)))
    methods = []
    # Only an Interac email its owner proved with an emailed code is ever shown to payers.
    if 'interac_email' in allowed and receiver.interac_email and getattr(receiver, 'interac_email_verified', False):
        from app.payment_security import mask_email
        methods.append({
            'type': 'interac',
            'label': 'Interac e-Transfer',
            'handle': receiver.interac_email,
            'masked': mask_email(receiver.interac_email),
            'verified': True,
            'url': None,
        })
    if 'paypal_username' in allowed and receiver.paypal_username:
        methods.append({
            'type': 'paypal',
            'label': 'PayPal',
            'handle': receiver.paypal_username,
            'url': f'https://paypal.me/{quote(receiver.paypal_username)}/{amount_text}{currency_code.upper()}',
        })
    if 'upi_id' in allowed and receiver.upi_id:
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


def normalize_phone(value):
    """'+1 (416) 555-0123' / '4165550123' -> '+14165550123'. Returns None if it isn't a plausible number."""
    raw = str(value or '').strip()
    digits = ''.join(char for char in raw if char.isdigit())
    if not raw.startswith('+') and len(digits) == 10:
        digits = '1' + digits  # A 10-digit number is North American.
    if not 10 <= len(digits) <= 15:
        return None
    return '+' + digits
