"""Purchase inbox: card purchases arrive as suggestions the user shares with a group or marks personal.

People turn on purchase alerts in their bank app and forward those emails to their own inbox address
(INBOX_EMAIL plus "+token"), or paste an alert's text into the app. Splitmate only reads the amount and
the store from the alert; it never connects to a bank and never holds or moves money.
"""
import email
import imaplib
import re
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape

from flask import current_app

from app import db
from app.email_utils import render_email, send_email
from app.models import InboxPurchase, User

# Read the mailbox at most this often (the server sleeps when idle, so it also checks when the inbox opens).
POLL_EVERY = timedelta(seconds=60)
_last_poll = {'at': None}

AMOUNT_RE = re.compile(r'(?:CA?\$|\$|CAD\s?)\s?(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)', re.I)
MERCHANT_LABEL_RE = re.compile(r'(?:merchant(?: name)?|store|retailer|description)\s*[:\-]\s*([^\n\r]{2,80})', re.I)
MERCHANT_AT_RE = re.compile(
    r'\bat\s+([A-Za-z0-9][^\n\r,]{1,70}?)(?=\s+(?:on|was|using|with|from|for|has|is)\b|[.,;!]\s|[.,;!]?$|\s*\n|\s{2,})',
    re.I | re.M,
)
REFUND_RE = re.compile(r'\b(refund|credit(?:ed)? to your|return|reversal|payment received|deposit)\b', re.I)


def inbox_address(user):
    """This user's forwarding address, or None when no inbox mailbox is set up on the server."""
    base = current_app.config.get('INBOX_EMAIL')
    if not base or '@' not in base:
        return None
    if not user.inbox_token:
        user.inbox_token = secrets.token_hex(5)
        db.session.commit()
    local, domain = base.split('@', 1)
    return f'{local}+{user.inbox_token}@{domain}'


def _clean_text(text):
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text or '', flags=re.S | re.I)
    text = re.sub(r'<br\s*/?>|</p>|</div>|</tr>|</td>', '\n', text, flags=re.I)
    text = unescape(re.sub(r'<[^>]+>', ' ', text))
    return re.sub(r'[ \t ]+', ' ', text)


def parse_purchase_alert(text):
    """Finds (amount, merchant) in a bank purchase alert, or None if it doesn't look like one."""
    text = _clean_text(text)
    if REFUND_RE.search(text) and not re.search(r'\bpurchase\b', text, re.I):
        return None
    amount_match = AMOUNT_RE.search(text)
    if not amount_match:
        return None
    try:
        amount = Decimal(amount_match.group(1).replace(',', '')).quantize(Decimal('0.01'))
    except InvalidOperation:
        return None
    if amount <= 0 or amount > Decimal('100000'):
        return None

    merchant = None
    label = MERCHANT_LABEL_RE.search(text)
    if label:
        merchant = label.group(1)
    else:
        # Prefer the "at STORE" that comes right after the amount, e.g. "a purchase of $12.50 at TIM HORTONS".
        after = MERCHANT_AT_RE.search(text, amount_match.end()) or MERCHANT_AT_RE.search(text)
        if after:
            merchant = after.group(1)
    merchant = re.sub(r'\s+', ' ', (merchant or '').strip(' .:-*')).strip()
    if not merchant or AMOUNT_RE.fullmatch(merchant):
        merchant = 'Card purchase'
    return amount, merchant[:200]


def add_purchase(user, amount, merchant, source, purchased_at=None, message_id=None):
    """Saves a suggestion unless the same email was already added. Returns the row or None."""
    if message_id and InboxPurchase.query.filter_by(user_id=user.id, message_id=message_id[:255]).first():
        return None
    purchase = InboxPurchase(
        user_id=user.id,
        amount=float(amount),
        merchant=merchant,
        source=source,
        purchased_at=purchased_at or datetime.utcnow(),
        message_id=message_id[:255] if message_id else None,
    )
    db.session.add(purchase)
    return purchase


def _decoded(value):
    try:
        return str(make_header(decode_header(value or '')))
    except Exception:
        return value or ''


def _message_text(message):
    parts = []
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_maintype() != 'text' or part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True) or b''
            parts.append(payload.decode(part.get_content_charset() or 'utf-8', errors='replace'))
        except Exception:
            continue
    return '\n'.join(parts)


def _token_from_recipients(message):
    base = (current_app.config.get('INBOX_EMAIL') or '').lower()
    local = base.split('@', 1)[0]
    headers = []
    for name in ('Delivered-To', 'X-Original-To', 'To', 'Cc', 'X-Forwarded-To'):
        headers.extend(message.get_all(name) or [])
    for _, address in getaddresses(headers):
        address = address.lower()
        if address.startswith(local + '+') and '@' in address:
            return address.split('@', 1)[0].split('+', 1)[1]
    return None


def _relay_forwarding_confirmation(user, subject, text):
    """Gmail and others email the new forwarding address a code; pass it on to the user."""
    code = re.search(r'confirmation code\s*[:\-]?\s*(\d{6,12})', text, re.I)
    link = re.search(r'https://mail(?:-settings)?\.google\.com/mail/[^\s<>"]+', text)
    lines = [f'Your email provider sent this to your Splitmate inbox: "{subject}".']
    if code:
        lines.append(f'Your confirmation code is {code.group(1)}. Enter it in your email settings to finish turning on forwarding.')
    if link:
        lines.append(f'Or open this link to confirm: {link.group(0)}')
    send_email(
        user.email,
        'Confirm forwarding to your Splitmate inbox',
        f'Hi {user.name},\n\n' + '\n\n'.join(lines) + '\n',
        render_email('Finish turning on forwarding to Splitmate.', 'Confirm forwarding', lines,
                     code=code.group(1) if code else None),
    )


def handle_inbox_message(raw_bytes):
    """Turns one received email into a suggestion. Returns 'added', 'confirm', or a reason it was skipped."""
    message = email.message_from_bytes(raw_bytes)
    token = _token_from_recipients(message)
    user = User.query.filter_by(inbox_token=token).first() if token else None
    if not user or user.is_suspended:
        return 'unknown_address'

    subject = _decoded(message.get('Subject'))
    text = _message_text(message)
    if re.search(r'forwarding confirmation|confirm.*forward', subject, re.I):
        _relay_forwarding_confirmation(user, subject, _clean_text(text))
        return 'confirm'

    parsed = parse_purchase_alert(f'{subject}\n{text}')
    if not parsed:
        return 'not_a_purchase'
    try:
        purchased_at = parsedate_to_datetime(message.get('Date')).replace(tzinfo=None)
    except Exception:
        purchased_at = None
    purchase = add_purchase(user, parsed[0], parsed[1], 'email', purchased_at,
                            message.get('Message-ID') or f'{subject}|{message.get("Date")}')
    db.session.commit()
    return 'added' if purchase else 'duplicate'


def poll_inbox(force=False):
    """Reads unread mail in the inbox mailbox over IMAP. Safe to call often; it throttles itself."""
    config = current_app.config
    if not (config.get('INBOX_EMAIL') and config.get('INBOX_IMAP_PASSWORD')):
        return {'enabled': False}
    now = datetime.utcnow()
    if not force and _last_poll['at'] and now - _last_poll['at'] < POLL_EVERY:
        return {'enabled': True, 'skipped': True}
    _last_poll['at'] = now

    results = {'enabled': True, 'added': 0, 'seen': 0}
    try:
        mailbox = imaplib.IMAP4_SSL(config['INBOX_IMAP_HOST'], timeout=15)
        mailbox.login(config['INBOX_EMAIL'], config['INBOX_IMAP_PASSWORD'])
        mailbox.select('INBOX')
        _, data = mailbox.search(None, 'UNSEEN')
        for number in (data[0].split() if data and data[0] else [])[:50]:
            _, fetched = mailbox.fetch(number, '(RFC822)')
            if not fetched or not isinstance(fetched[0], tuple):
                continue
            results['seen'] += 1
            try:
                if handle_inbox_message(fetched[0][1]) == 'added':
                    results['added'] += 1
            except Exception as exc:
                current_app.logger.exception('Could not read an inbox email: %s', exc)
                db.session.rollback()
        db.session.commit()
        mailbox.logout()
    except Exception as exc:
        current_app.logger.warning('Purchase inbox check failed: %s', exc)
        db.session.rollback()
        results['error'] = True
    return results
