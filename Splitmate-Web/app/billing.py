"""Splitmate Pro through Stripe Checkout. Stripe holds the card details; we only store ids and status.

Prices live in config (PRO_PRICE_MONTHLY_CENTS / PRO_PRICE_YEARLY_CENTS), so changing them on Render needs
no code change. A webhook from Stripe is the only thing that turns Pro on or off.
"""
from datetime import datetime
import hashlib
import json
import time

import stripe
from flask import current_app

from app import db
from app.models import FeatureUsage, User

PRO_STATUSES = {'active', 'trialing', 'past_due'}
INTERVALS = ('month', 'year')
FREE_FEATURES = [
    'Split expenses, tasks and notes',
    'Quick split with friends',
    'Settle up with Interac, PayPal or UPI',
]
PRO_FEATURES = [
    'Unlimited receipt scanning',
    'Unlimited grocery price comparison',
    'Supports Splitmate, no ads ever',
]


FEATURE_LIMITS = {
    'receipt_scan': ('FREE_RECEIPT_SCANS_PER_MONTH', 'receipt scans'),
    'grocery_compare': ('FREE_GROCERY_COMPARES_PER_MONTH', 'grocery price comparisons'),
}


def _month():
    return datetime.utcnow().strftime('%Y-%m')


def feature_usage(user, feature):
    """{'used', 'limit', 'remaining'} for this month; limit and remaining are None for Pro (unlimited)."""
    row = FeatureUsage.query.filter_by(user_id=user.id, feature=feature, month=_month()).first()
    used = row.count if row else 0
    if is_pro(user):
        return {'used': used, 'limit': None, 'remaining': None}
    limit = int(current_app.config[FEATURE_LIMITS[feature][0]])
    return {'used': used, 'limit': limit, 'remaining': max(limit - used, 0)}


def feature_limit_error(user, feature):
    """The message to show when a free user has used up this month's allowance, else None."""
    usage = feature_usage(user, feature)
    if usage['remaining'] == 0:
        return (f'You have used all {usage["limit"]} free {FEATURE_LIMITS[feature][1]} this month. '
                'Upgrade to Splitmate Pro for unlimited use, or wait until next month.')
    return None


def record_feature_use(user, feature):
    row = FeatureUsage.query.filter_by(user_id=user.id, feature=feature, month=_month()).first()
    if row is None:
        row = FeatureUsage(user_id=user.id, feature=feature, month=_month(), count=0)
        db.session.add(row)
    row.count += 1
    db.session.commit()
    return feature_usage(user, feature)


def billing_enabled():
    return bool(current_app.config.get('STRIPE_SECRET_KEY'))


def _currency():
    return (current_app.config.get('STRIPE_CURRENCY') or 'cad').lower()


def price_cents(interval):
    key = 'PRO_PRICE_MONTHLY_CENTS' if interval == 'month' else 'PRO_PRICE_YEARLY_CENTS'
    return int(current_app.config[key])


def _money(cents):
    prefix = 'CA$' if _currency() == 'cad' else f'{_currency().upper()} '
    return f'{prefix}{cents / 100:.2f}' if cents else f'{prefix}0'


def price_label(interval):
    return _money(price_cents(interval))


def is_pro(user):
    return user.membership_plan == 'pro' and user.membership_status in PRO_STATUSES


def membership_plans(user):
    """Free plus one Pro card per billing interval, marked current for the user's own plan."""
    yearly_saving = round(100 - price_cents('year') * 100 / (price_cents('month') * 12))
    pro = is_pro(user)
    plans = [{
        'id': 'free', 'name': 'Free', 'price': _money(0), 'interval': 'forever',
        'badge': 'Always free', 'features': FREE_FEATURES + [
            f'{current_app.config["FREE_RECEIPT_SCANS_PER_MONTH"]} receipt scans a month',
            f'{current_app.config["FREE_GROCERY_COMPARES_PER_MONTH"]} grocery price comparisons a month',
        ], 'checkout_interval': None,
        'is_current': not pro,
    }]
    for interval, badge in (('month', 'Flexible'), ('year', f'Save {yearly_saving}%')):
        plans.append({
            'id': f'pro_{interval}', 'name': 'Splitmate Pro', 'price': price_label(interval), 'interval': interval,
            'badge': badge, 'features': PRO_FEATURES, 'checkout_interval': interval,
            'is_current': pro and user.membership_interval == interval,
        })
    return plans


def membership_payload(user):
    return {
        'membership_plan': 'pro' if is_pro(user) else 'free',
        'membership_status': user.membership_status or 'active',
        'membership_interval': user.membership_interval or '',
        'membership_renews_at': user.membership_renews_at.isoformat() if user.membership_renews_at else None,
        'membership_cancel_at_period_end': bool(user.membership_cancel_at_period_end),
        'billing_enabled': billing_enabled(),
        'membership_plans': membership_plans(user),
        'usage': {feature: feature_usage(user, feature) for feature in FEATURE_LIMITS},
    }


def _ensure_customer(user):
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            api_key=current_app.config['STRIPE_SECRET_KEY'],
            email=user.email, name=user.name, metadata={'user_id': str(user.id)},
            idempotency_key=f'splitmate-customer-{user.id}',
        )
        user.stripe_customer_id = customer.id
        db.session.commit()
    return user.stripe_customer_id


def checkout_idempotency_key(user, interval, success_url, cancel_url):
    """The same tap repeated within five minutes gets Stripe's first answer back, never a second session."""
    window = int(time.time() // 300)
    raw = f'{user.id}|{interval}|{price_cents(interval)}|{_currency()}|{success_url}|{cancel_url}|{window}'
    return 'splitmate-checkout-' + hashlib.sha256(raw.encode()).hexdigest()[:32]


def create_checkout_url(user, interval, success_url, cancel_url):
    """Returns (url, error). The page is hosted by Stripe; Pro turns on when its webhook arrives."""
    if not billing_enabled():
        return None, 'Payments are not set up yet. Try again later.'
    if interval not in INTERVALS:
        return None, 'Choose monthly or yearly.'
    if is_pro(user):
        return None, 'You already have Splitmate Pro. Use Manage subscription to change it.'
    session = stripe.checkout.Session.create(
        api_key=current_app.config['STRIPE_SECRET_KEY'],
        mode='subscription',
        customer=_ensure_customer(user),
        client_reference_id=str(user.id),
        line_items=[{
            'quantity': 1,
            'price_data': {
                'currency': _currency(),
                'unit_amount': price_cents(interval),
                'recurring': {'interval': interval},
                'product_data': {'name': 'Splitmate Pro'},
            },
        }],
        subscription_data={'metadata': {'user_id': str(user.id)}},
        metadata={'user_id': str(user.id)},
        success_url=success_url,
        cancel_url=cancel_url,
        idempotency_key=checkout_idempotency_key(user, interval, success_url, cancel_url),
    )
    return session.url, None


def create_portal_url(user, return_url):
    """Stripe's own page for changing the card, switching plan or cancelling."""
    if not billing_enabled():
        return None, 'Payments are not set up yet. Try again later.'
    if not user.stripe_customer_id:
        return None, 'You have no subscription to manage.'
    session = stripe.billing_portal.Session.create(
        api_key=current_app.config['STRIPE_SECRET_KEY'],
        customer=user.stripe_customer_id,
        return_url=return_url,
    )
    return session.url, None


def _user_for(obj):
    user_id = (obj.get('metadata') or {}).get('user_id') or obj.get('client_reference_id')
    user = db.session.get(User, int(user_id)) if user_id and str(user_id).isdigit() else None
    if user is None and obj.get('customer'):
        user = User.query.filter_by(stripe_customer_id=obj['customer']).first()
    return user


def _apply_subscription(user, subscription):
    status = subscription.get('status') or 'canceled'
    items = (subscription.get('items') or {}).get('data') or [{}]
    item = items[0]
    period_end = subscription.get('current_period_end') or item.get('current_period_end')
    user.stripe_customer_id = subscription.get('customer') or user.stripe_customer_id
    user.stripe_subscription_id = subscription.get('id')
    user.membership_plan = 'pro' if status in PRO_STATUSES else 'free'
    user.membership_status = status if status in PRO_STATUSES else 'active'
    user.membership_interval = ((item.get('price') or {}).get('recurring') or {}).get('interval') if status in PRO_STATUSES else None
    user.membership_renews_at = datetime.utcfromtimestamp(period_end) if period_end and status in PRO_STATUSES else None
    user.membership_cancel_at_period_end = bool(subscription.get('cancel_at_period_end')) and status in PRO_STATUSES


def handle_webhook(payload, signature):
    """Verifies Stripe's signature, then applies the event. Returns (ok, message)."""
    secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    if not secret:
        return False, 'Webhook secret is not configured.'
    try:
        stripe.WebhookSignature.verify_header(payload, signature or '', secret, tolerance=300)
    except stripe.SignatureVerificationError:
        return False, 'Invalid signature.'
    event = json.loads(payload)
    obj = (event.get('data') or {}).get('object') or {}
    kind = event.get('type')

    newly_pro = None
    if kind == 'checkout.session.completed' and obj.get('mode') == 'subscription':
        user = _user_for(obj)
        if user and obj.get('customer'):
            user.stripe_customer_id = obj['customer']
    elif kind in ('customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted'):
        user = _user_for(obj)
        # An older subscription ending must not switch off a newer, still-running one.
        stale = (user is not None and user.stripe_subscription_id not in (None, obj.get('id'))
                 and is_pro(user) and obj.get('status') not in PRO_STATUSES)
        if user and not stale:
            was_pro = is_pro(user)
            _apply_subscription(user, obj)
            if is_pro(user) and not was_pro:
                newly_pro = user
    db.session.commit()
    if newly_pro:
        _send_welcome_to_pro(newly_pro)
    return True, 'ok'


def _send_welcome_to_pro(user):
    """Confirmation email once Pro switches on. Best effort: Stripe has already taken the payment."""
    from app.email_utils import send_membership_confirmation_email
    interval = user.membership_interval or 'month'
    try:
        send_membership_confirmation_email(
            user,
            'Splitmate Pro',
            renews_on=user.membership_renews_at.strftime('%b %d, %Y') if user.membership_renews_at else None,
            amount_text=f'{price_label(interval)} / {interval}',
        )
    except Exception as exc:
        current_app.logger.exception('Failed to send Pro welcome email: %s', exc)
