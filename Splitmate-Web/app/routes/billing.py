"""Website side of Splitmate Pro, plus the Stripe webhook that both the app and website rely on."""
from flask import Blueprint, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required

from app import billing, limiter

billing_bp = Blueprint('billing', __name__)


def _profile_url(query=''):
    return url_for('main.profile', _external=True) + query + '#membership-panel'


@billing_bp.route('/membership/checkout', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def checkout():
    try:
        url, error = billing.create_checkout_url(
            current_user, request.form.get('interval'),
            success_url=_profile_url('?membership=success'),
            cancel_url=_profile_url('?membership=cancelled'),
        )
    except Exception as exc:
        current_app.logger.exception('Stripe checkout failed: %s', exc)
        url, error = None, 'Could not open the payment page. Try again in a minute.'
    if error:
        flash(error, 'error')
        return redirect(_profile_url())
    return redirect(url, code=303)


@billing_bp.route('/membership/portal', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def portal():
    try:
        url, error = billing.create_portal_url(current_user, _profile_url())
    except Exception as exc:
        current_app.logger.exception('Stripe portal failed: %s', exc)
        url, error = None, 'Could not open subscription settings. Try again in a minute.'
    if error:
        flash(error, 'error')
        return redirect(_profile_url())
    return redirect(url, code=303)


@billing_bp.route('/stripe/webhook', methods=['POST'])
@limiter.exempt
def stripe_webhook():
    ok, message = billing.handle_webhook(request.get_data(as_text=True), request.headers.get('Stripe-Signature'))
    if not ok:
        current_app.logger.warning('Rejected Stripe webhook: %s', message)
        return {'error': message}, 400
    return {'received': True}
